"""Paper-trading executor — computes simulated fills and records them in a Portfolio.

Implements BaseTradingExecutor. Models commission (turnover-based Indian-equity
charges + optional flat fee) and slippage, opens one position per symbol, and
auto-closes on stop-loss/target. All account STATE (cash, positions, P&L, metrics,
persistence) lives in ``src/portfolio/book.py``; this class only decides fills and
records them via ``self.book``. The read methods delegate to the book, so a future
live executor can reuse the same Portfolio unchanged.

Entry points: ``execute_trade(signal, price)`` is the signal-based path the AI
pipeline uses; ``execute_simple_trade(...)`` and the contract ``place_order(...)``
are thin convenience wrappers over it.
"""

from datetime import datetime
from typing import Dict, Optional, Any

from src.platform.types import BaseTradingExecutor
from src.platform.config import (
    INITIAL_CAPITAL, PAPER_TRADE_COMMISSION, PAPER_TRADE_SLIPPAGE, TRADING_PRODUCT,
    EMERGENCY_STOP_LOSS_PCT, EMERGENCY_TAKE_PROFIT_PCT, EMERGENCY_RECHECK_PCT,
)
from src.execution.costs import compute_charges
from src.portfolio.book import Portfolio, PaperTrade
from src.platform.logger import setup_logger
from src.platform.events import log_event
from src.monitoring.performance import performance_tracker

logger = setup_logger(__name__, 'paper_trader.log')


class PaperTrader(BaseTradingExecutor):
    """Paper-trading executor: simulates fills against a Portfolio book."""

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.book = Portfolio(initial_capital)

    def place_order(self, symbol: str, quantity: int, order_type: str,
                    price: Optional[float] = None) -> Dict[str, Any]:
        """BaseTradingExecutor entry point — a paper fill needs an explicit price.

        Delegates to execute_simple_trade (the shared simple-order path) rather
        than being an interface-only stub.
        """
        if price is None:
            return {"status": "REJECTED", "reason": "Paper trading requires an explicit fill price"}
        return self.execute_simple_trade(symbol, order_type, price, quantity)

    @performance_tracker("trade_execution")
    def execute_trade(self, signal: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Execute a paper trade based on an AI signal."""
        try:
            symbol = signal.get('symbol')
            action = signal.get('signal')  # BUY, SELL, HOLD

            # Reject a signal with no symbol up front: otherwise a malformed
            # signal opens a phantom position keyed by None ("BUY executed: None").
            if not symbol:
                return {"status": "REJECTED", "reason": "Signal missing 'symbol'"}

            if action == 'HOLD':
                return {"status": "SKIPPED", "reason": "HOLD signal - no action taken"}

            # Execution price with slippage
            slippage_amount = current_price * PAPER_TRADE_SLIPPAGE
            execution_price = current_price + slippage_amount if action == 'BUY' else current_price - slippage_amount

            quantity = signal.get('position_size', 1)
            stop_loss = signal.get('stop_loss')
            target = signal.get('target')

            # A SELL always closes the whole position (see _execute_sell), so the
            # requested size is irrelevant — and an AI/rule-based signal may carry a
            # null or oversized position_size that would otherwise crash or trip the
            # "cannot sell N shares" gate below. Size the exit to the actual holding.
            if action == 'SELL' and symbol in self.book.open_positions:
                quantity = self.book.open_positions[symbol].quantity

            validation = self._validate_trade(symbol, action, quantity, execution_price)
            if not validation['valid']:
                return {"status": "REJECTED", "reason": validation['reason']}

            if action == 'BUY':
                return self._execute_buy(symbol, quantity, execution_price, stop_loss, target, signal)
            elif action == 'SELL':
                return self._execute_sell(symbol, quantity, execution_price, signal)

        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {"status": "ERROR", "message": str(e)}

    def execute_simple_trade(self, symbol: str, action: str, price: float, quantity: int = 1,
                             stop_loss: Optional[float] = None, target: Optional[float] = None) -> Dict[str, Any]:
        """Execute a simple trade (for testing and manual trading)."""
        signal = {
            'symbol': symbol,
            'signal': action.upper(),
            'position_size': quantity,
            'stop_loss': stop_loss,
            'target': target,
            'confidence': 1.0,
            'reasoning': 'Manual/Test trade',
            'indicators': {},
        }
        return self.execute_trade(signal, price)

    def _execute_buy(self, symbol: str, quantity: int, price: float,
                     stop_loss: Optional[float], target: Optional[float],
                     signal: Dict[str, Any]) -> Dict[str, Any]:
        """Compute a BUY fill and record it in the book."""
        if symbol in self.book.open_positions:
            return {"status": "REJECTED", "reason": "Already have open position in this symbol"}

        # Charges are levied on the actual fill turnover (price already includes
        # slippage); PAPER_TRADE_COMMISSION is an optional extra flat fee (default 0).
        position_value = quantity * price
        commission = compute_charges(position_value, "BUY", TRADING_PRODUCT) + PAPER_TRADE_COMMISSION
        total_cost = position_value + commission

        if total_cost > self.book.available_capital:
            return {"status": "REJECTED",
                    "reason": f"Insufficient capital. Need ₹{total_cost:.2f}, have ₹{self.book.available_capital:.2f}"}

        # Emergency thresholds from the signal (AI-revisable per cycle).
        emergency = signal.get('emergency_thresholds', {})
        trade = PaperTrade(
            trade_id=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}_BUY",
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            entry_price=price,
            current_price=price,
            stop_loss=stop_loss,
            target=target,
            commission=commission,
            slippage=price * PAPER_TRADE_SLIPPAGE,
            position_value=position_value,
            emergency_stop_loss_pct=emergency.get('stop_loss_pct', EMERGENCY_STOP_LOSS_PCT),
            emergency_take_profit_pct=emergency.get('take_profit_pct', EMERGENCY_TAKE_PROFIT_PCT),
            emergency_recheck_pct=emergency.get('recheck_trigger_pct', EMERGENCY_RECHECK_PCT),
            ai_monitoring_comment=emergency.get('comment'),
            signal_strength=signal.get('signal_strength', 0),
            confidence=signal.get('confidence', 0),
            reasoning=signal.get('reasoning', ''),
            indicators=signal.get('indicators', {}),
            status="OPEN",
            unrealized_pnl=0.0,
            pnl_percent=0.0,
        )

        self.book.open(trade, total_cost)
        logger.info(f"BUY executed: {symbol} x{quantity} @ ₹{price:.2f}")
        log_event('fill', action='BUY', symbol=symbol, quantity=quantity,
                  price=round(price, 2), value=round(position_value, 2),
                  commission=round(commission, 2))
        return {
            "status": "EXECUTED", "trade_id": trade.trade_id, "action": "BUY",
            "symbol": symbol, "quantity": quantity, "price": price,
            "commission": commission, "total_cost": total_cost,
            "stop_loss": stop_loss, "target": target,
        }

    def _execute_sell(self, symbol: str, quantity: int, price: float,
                      signal: Dict[str, Any]) -> Dict[str, Any]:
        """Compute a SELL fill (full close) and record it in the book."""
        if symbol not in self.book.open_positions:
            return {"status": "REJECTED", "reason": "No open position to sell"}

        position = self.book.open_positions[symbol]
        # A SELL closes the whole position. The requested quantity from an AI SELL
        # is unreliable (sized as if opening) and partial exits don't fit the
        # one-record-per-position model, so exit in full — consistent with the
        # stop-loss / target auto-closes.
        quantity = position.quantity

        # Sell-side charges differ from buy-side (delivery STT both sides, DP charge
        # on delivery sells, no stamp duty).
        gross_proceeds = quantity * price
        commission = compute_charges(gross_proceeds, "SELL", TRADING_PRODUCT) + PAPER_TRADE_COMMISSION
        net_proceeds = gross_proceeds - commission

        result = self.book.close(symbol, price, net_proceeds, commission,
                                 exit_reason=signal.get('exit_reason', 'SIGNAL'))

        logger.info(
            f"SELL executed: {symbol} x{quantity} @ ₹{price:.2f} "
            f"P&L: ₹{result['realized_pnl']:.2f} ({result['pnl_percent']:+.2f}%)"
        )
        log_event('fill', action='SELL', symbol=symbol, quantity=quantity,
                  price=round(price, 2), pnl=round(result['realized_pnl'], 2),
                  pnl_pct=round(result['pnl_percent'], 2),
                  reason=signal.get('exit_reason', 'SIGNAL'))
        return {
            "status": "EXECUTED", "trade_id": position.trade_id, "action": "SELL",
            "symbol": symbol, "quantity": quantity, "price": price,
            "commission": commission,
            "realized_pnl": result['realized_pnl'], "pnl_percent": result['pnl_percent'],
        }

    def update_positions(self, current_prices: Dict[str, float]) -> list:
        """Mark positions to market, then auto-close any that hit stop-loss/target.

        This is the mechanical SAFETY FLOOR: it must run every tick so a position
        is guaranteed to exit at its hard stop/target even when the AI/alert layer
        doesn't act. Returns the list of auto-close fill results (each tagged with
        ``symbol`` + ``exit_reason``) so the caller can record them and refresh any
        derived state; empty when nothing closed.
        """
        self.book.mark_to_market(current_prices)
        closed = []
        # Iterate a copy: _execute_sell deletes from open_positions.
        for symbol, position in list(self.book.open_positions.items()):
            price = current_prices.get(symbol)
            if price is None:
                continue
            reason = None
            if position.stop_loss and price <= position.stop_loss:
                logger.warning(f"Stop loss triggered for {symbol}")
                reason = "STOP_LOSS"
            elif position.target and price >= position.target:
                logger.info(f"Target reached for {symbol}")
                reason = "TARGET_HIT"
            if reason:
                result = self._execute_sell(symbol, position.quantity, price, {"exit_reason": reason})
                result.update(symbol=symbol, exit_reason=reason)
                closed.append(result)
        return closed

    def _validate_trade(self, symbol: str, action: str, quantity: int, price: float) -> Dict[str, Any]:
        """Validate trade parameters before execution (reads book state)."""
        try:
            if quantity <= 0:
                return {"valid": False, "reason": "Invalid quantity - insufficient capital for position"}
            if price <= 0:
                return {"valid": False, "reason": "Invalid price"}

            if action == 'BUY':
                total_cost = quantity * price + PAPER_TRADE_COMMISSION
                if total_cost > self.book.available_capital:
                    return {"valid": False,
                            "reason": f"Insufficient capital. Need ₹{total_cost:.2f}, have ₹{self.book.available_capital:.2f}"}
                if symbol in self.book.open_positions:
                    return {"valid": False, "reason": "Already have open position in this symbol"}

            elif action == 'SELL':
                if symbol not in self.book.open_positions:
                    return {"valid": False, "reason": "No open position to sell"}
                if quantity > self.book.open_positions[symbol].quantity:
                    return {"valid": False,
                            "reason": f"Cannot sell {quantity} shares, only have {self.book.open_positions[symbol].quantity}"}

            return {"valid": True, "reason": "OK"}
        except Exception as e:
            return {"valid": False, "reason": f"Validation error: {str(e)}"}

    # ----- read APIs delegate to the portfolio book -----

    def get_positions(self) -> Dict[str, Any]:
        return self.book.get_positions()

    def has_position(self, symbol: str) -> bool:
        return self.book.has_position(symbol)

    def get_account_info(self) -> Dict[str, Any]:
        return self.book.get_account_info()

    def generate_performance_report(self) -> Dict[str, Any]:
        return self.book.generate_performance_report()
