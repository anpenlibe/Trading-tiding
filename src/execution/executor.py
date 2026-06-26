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
    MIN_TRADE_VALUE,
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

            # MOVE_STOP touches no price/fill — it only mutates the stop level.
            if action == 'MOVE_STOP':
                return self._execute_move_stop(symbol, signal, current_price)

            # Execution price with slippage: buy-side (pay up) for BUY/ADD, sell-side
            # (receive less) for SELL/TRIM.
            buy_side = action in ('BUY', 'ADD')
            slippage_amount = current_price * PAPER_TRADE_SLIPPAGE
            execution_price = current_price + slippage_amount if buy_side else current_price - slippage_amount

            if action == 'ADD':
                return self._execute_add(symbol, signal, execution_price)
            if action == 'TRIM':
                return self._execute_trim(symbol, signal, execution_price)

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

            return {"status": "REJECTED", "reason": f"Unknown signal '{action}'"}

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
            total_buy_quantity=quantity,
            # Seed thesis memory from the decision's reasoning (the field the model
            # emits today); the prompt rewrite later supplies structured thesis fields.
            entry_thesis=signal.get('entry_thesis') or signal.get('reasoning', ''),
            thesis=signal.get('thesis') or signal.get('reasoning', ''),
            thesis_status=signal.get('thesis_status', 'intact'),
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

    def _execute_add(self, symbol: str, signal: Dict[str, Any], price: float) -> Dict[str, Any]:
        """Scale into an existing position (ADD). The increment was sized by the risk
        manager (aggregate-capped) and stamped onto ``position_size``; re-average + debit."""
        if symbol not in self.book.open_positions:
            return {"status": "REJECTED", "reason": "No open position to ADD to"}

        add_qty = signal.get('position_size', 0) or 0
        if add_qty <= 0:
            return {"status": "REJECTED", "reason": "ADD requires a positive sized increment"}

        position_value = add_qty * price
        commission = compute_charges(position_value, "BUY", TRADING_PRODUCT) + PAPER_TRADE_COMMISSION
        total_cost = position_value + commission
        if total_cost > self.book.available_capital:
            return {"status": "REJECTED",
                    "reason": f"Insufficient capital for ADD. Need ₹{total_cost:.2f}, have ₹{self.book.available_capital:.2f}"}

        self.book.add_to_position(symbol, add_qty, price, commission, total_cost)
        # Scaling in is a fresh expression of conviction — evolve the thesis to match.
        new_thesis = signal.get('thesis') or signal.get('reasoning')
        if new_thesis or signal.get('thesis_status'):
            self.book.update_thesis(symbol, thesis=new_thesis, status=signal.get('thesis_status'))
        pos = self.book.open_positions[symbol]
        logger.info(f"ADD executed: {symbol} x{add_qty} @ ₹{price:.2f} "
                    f"(now {pos.quantity} @ avg ₹{pos.entry_price:.2f})")
        log_event('fill', action='ADD', symbol=symbol, quantity=add_qty,
                  price=round(price, 2), value=round(position_value, 2),
                  commission=round(commission, 2), new_quantity=pos.quantity,
                  new_avg_price=round(pos.entry_price, 2))
        return {
            "status": "EXECUTED", "trade_id": pos.trade_id, "action": "ADD",
            "symbol": symbol, "quantity": add_qty, "price": price, "commission": commission,
            "new_quantity": pos.quantity, "new_avg_price": pos.entry_price,
        }

    def _execute_trim(self, symbol: str, signal: Dict[str, Any], price: float) -> Dict[str, Any]:
        """Partial exit (TRIM): realize ``trim_fraction`` of the holding against average
        cost, keep the remainder open. Escalates to a full SELL if the trim would take
        everything or leave a sub-MIN_TRADE_VALUE remnant (uneconomic to exit later)."""
        if symbol not in self.book.open_positions:
            return {"status": "REJECTED", "reason": "No open position to TRIM"}

        position = self.book.open_positions[symbol]
        try:
            frac = float(signal.get('trim_fraction', 0.5))
        except (TypeError, ValueError):
            frac = 0.5
        frac = max(0.0, min(1.0, frac))
        trim_qty = int(position.quantity * frac)
        if trim_qty <= 0:
            return {"status": "REJECTED",
                    "reason": f"Trim fraction {frac:.2f} too small for {position.quantity} shares"}

        remainder_value = (position.quantity - trim_qty) * position.entry_price
        if trim_qty >= position.quantity or remainder_value < MIN_TRADE_VALUE:
            # Don't leave an unsellable remnant — exit in full instead.
            return self._execute_sell(symbol, position.quantity, price,
                                      {"exit_reason": signal.get('exit_reason', 'TRIM_FULL')})

        gross_proceeds = trim_qty * price
        commission = compute_charges(gross_proceeds, "SELL", TRADING_PRODUCT) + PAPER_TRADE_COMMISSION
        net_proceeds = gross_proceeds - commission
        result = self.book.close(symbol, price, net_proceeds, commission,
                                 exit_reason='TRIM', quantity=trim_qty)

        logger.info(f"TRIM executed: {symbol} x{trim_qty} @ ₹{price:.2f} "
                    f"P&L: ₹{result['realized_pnl']:.2f}; {result['remaining_quantity']} left")
        log_event('fill', action='TRIM', symbol=symbol, quantity=trim_qty,
                  price=round(price, 2), pnl=round(result['realized_pnl'], 2),
                  pnl_pct=round(result['pnl_percent'], 2),
                  remaining_quantity=result['remaining_quantity'], reason='TRIM')
        return {
            "status": "EXECUTED", "trade_id": position.trade_id, "action": "TRIM",
            "symbol": symbol, "quantity": trim_qty, "price": price, "commission": commission,
            "realized_pnl": result['realized_pnl'], "pnl_percent": result['pnl_percent'],
            "remaining_quantity": result['remaining_quantity'],
        }

    def _execute_move_stop(self, symbol: str, signal: Dict[str, Any],
                           current_price: float) -> Dict[str, Any]:
        """Tighten-only stop move. Rejects a loosening move and any stop at/above market
        (a stop >= price is a disguised market exit — the next floor pass would close it
        at the stop, a worse fill than a clean SELL). No cash/fill."""
        if symbol not in self.book.open_positions:
            return {"status": "REJECTED", "reason": "No open position to MOVE_STOP"}

        new_stop = signal.get('new_stop')
        if new_stop is None:
            return {"status": "REJECTED", "reason": "MOVE_STOP requires 'new_stop'"}
        try:
            new_stop = float(new_stop)
        except (TypeError, ValueError):
            return {"status": "REJECTED", "reason": "new_stop is not numeric"}

        old_stop = self.book.open_positions[symbol].stop_loss
        if new_stop >= current_price:
            return {"status": "REJECTED",
                    "reason": f"new_stop ₹{new_stop:.2f} >= price ₹{current_price:.2f} (would insta-trigger)"}
        if old_stop is not None and new_stop <= old_stop:
            return {"status": "REJECTED",
                    "reason": f"new_stop ₹{new_stop:.2f} does not tighten (current ₹{old_stop:.2f})"}

        self.book.set_stop(symbol, new_stop)
        logger.info(f"MOVE_STOP: {symbol} stop {old_stop} -> ₹{new_stop:.2f}")
        log_event('management', action='MOVE_STOP', symbol=symbol,
                  old_stop=round(old_stop, 2) if old_stop is not None else None,
                  new_stop=round(new_stop, 2))
        return {
            "status": "EXECUTED", "action": "MOVE_STOP", "symbol": symbol,
            "old_stop": old_stop, "new_stop": new_stop,
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

    def update_thesis(self, symbol: str, thesis: Optional[str] = None,
                      status: Optional[str] = None):
        """Persist an evolving thesis/status onto a held position (e.g. a HOLD that
        reports the thesis is now 'weakening'). Delegates to the book."""
        self.book.update_thesis(symbol, thesis=thesis, status=status)

    def get_positions(self) -> Dict[str, Any]:
        return self.book.get_positions()

    def has_position(self, symbol: str) -> bool:
        return self.book.has_position(symbol)

    def get_account_info(self) -> Dict[str, Any]:
        return self.book.get_account_info()

    def generate_performance_report(self) -> Dict[str, Any]:
        return self.book.generate_performance_report()
