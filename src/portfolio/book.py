"""Portfolio book — the trading-account STATE, independent of how fills happen.

Holds cash, open/closed positions, realized/unrealized P&L, performance metrics,
and trade persistence. An executor (paper now, live later) computes fills and
records them here via ``open()`` / ``close()`` / ``mark_to_market()``. Separating
state from fill logic lets a live executor reuse the same book, and lets the
decision layer be fed a portfolio ``snapshot()`` (holdings + cash) for
better-informed calls — the "what we own / how much money we have" the notes ask for.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import pandas as pd

from src.platform.config import (
    INITIAL_CAPITAL, EMERGENCY_STOP_LOSS_PCT, EMERGENCY_TAKE_PROFIT_PCT, EMERGENCY_RECHECK_PCT,
)
from src.platform.logger import setup_logger, LOGS_DIR

logger = setup_logger(__name__, 'portfolio.log')


@dataclass
class PaperTrade:
    """One position/trade record (open → closed)."""
    trade_id: str
    timestamp: str
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: Optional[float]
    target: Optional[float]
    commission: float
    slippage: float
    position_value: float

    # Decision context
    signal_strength: float
    confidence: float
    reasoning: str
    indicators: Dict[str, float]

    # Status (required field)
    status: str  # OPEN, CLOSED

    # Emergency thresholds (percentages from entry price)
    emergency_stop_loss_pct: float = EMERGENCY_STOP_LOSS_PCT
    emergency_take_profit_pct: float = EMERGENCY_TAKE_PROFIT_PCT
    emergency_recheck_pct: float = EMERGENCY_RECHECK_PCT
    ai_monitoring_comment: Optional[str] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_reason: Optional[str] = None  # TARGET_HIT, STOP_LOSS, MANUAL

    # P&L
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    pnl_percent: Optional[float] = None


class Portfolio:
    """Account state: cash, positions, realized/unrealized P&L, and metrics."""

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.available_capital = initial_capital

        self.open_positions: Dict[str, PaperTrade] = {}
        self.closed_trades: List[PaperTrade] = []
        self.all_trades: List[PaperTrade] = []

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = 0.0
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0

        # Use the logger's canonical repo-root data/logs (NOT src/data/logs): the
        # old dirname(dirname(__file__)) resolved to src/, splitting account state
        # away from the logs the monitor reads. One logs dir, one source of truth.
        self.trade_log_file = os.path.join(LOGS_DIR, 'paper_trades.json')
        os.makedirs(os.path.dirname(self.trade_log_file), exist_ok=True)

        logger.info(f"Portfolio initialized with capital: ₹{initial_capital}")

    # ----- state mutations (an executor records fills through these) -----

    def open(self, trade: PaperTrade, total_cost: float):
        """Record a newly-opened position and debit its total cost from cash."""
        self.available_capital -= total_cost
        self.total_commission += trade.commission
        self.open_positions[trade.symbol] = trade
        self.all_trades.append(trade)
        self.total_trades += 1
        self.recompute()
        self._log_trade(trade)

    def close(self, symbol: str, exit_price: float, net_proceeds: float,
              commission: float, exit_reason: str = 'SIGNAL') -> Dict[str, float]:
        """Close the whole position, credit net proceeds, realize P&L. Returns the
        realized P&L. Recompute happens AFTER the del so the closed position's
        proceeds (already in cash) aren't double-counted in current_capital."""
        position = self.open_positions[symbol]
        cost_basis = position.entry_price * position.quantity
        realized_pnl = net_proceeds - cost_basis - position.commission
        pnl_percent = (realized_pnl / cost_basis) * 100

        position.exit_price = exit_price
        position.exit_timestamp = datetime.now().isoformat()
        position.exit_reason = exit_reason
        position.realized_pnl = realized_pnl
        position.pnl_percent = pnl_percent
        position.status = "CLOSED"

        self.available_capital += net_proceeds
        self.total_commission += commission
        # A break-even close (exactly 0) is a scratch — neither win nor loss. Keeping
        # it out of losing_trades stops it diluting avg_loss (which divides by that
        # count); win_rate uses total closed as its denominator, so a scratch still
        # correctly counts as a non-win there.
        if realized_pnl > 0:
            self.winning_trades += 1
        elif realized_pnl < 0:
            self.losing_trades += 1

        self.closed_trades.append(position)
        del self.open_positions[symbol]
        self.recompute()
        self._log_trade(position)

        return {"realized_pnl": realized_pnl, "pnl_percent": pnl_percent}

    def mark_to_market(self, current_prices: Dict[str, float]):
        """Refresh unrealized P&L for open positions, then recompute capital."""
        for symbol, position in self.open_positions.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                position.current_price = current_price
                cost_basis = position.quantity * position.entry_price
                position.unrealized_pnl = position.quantity * current_price - cost_basis - position.commission
                position.pnl_percent = (position.unrealized_pnl / cost_basis) * 100
        self.recompute()

    def recompute(self):
        """current_capital = cash + mark-to-market value of open positions; refresh
        peak capital and max drawdown so account metrics stay current."""
        self.current_capital = self.available_capital + sum(
            pos.quantity * pos.current_price for pos in self.open_positions.values()
        )
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    # ----- reads -----

    def has_position(self, symbol: str) -> bool:
        """Checks if an open position exists for the given symbol."""
        return symbol in self.open_positions and self.open_positions[symbol].quantity > 0

    def get_positions(self) -> Dict[str, Any]:
        """Current open positions and their status."""
        return {
            symbol: {
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "unrealized_pnl": p.unrealized_pnl,
                "pnl_percent": p.pnl_percent,
                "stop_loss": p.stop_loss,
                "target": p.target,
                "entry_time": p.timestamp,
                "emergency_recheck_pct": p.emergency_recheck_pct,
            }
            for symbol, p in self.open_positions.items()
        }

    def snapshot(self) -> Dict[str, Any]:
        """Compact portfolio view for feeding the decision layer (holdings + cash)."""
        return {
            "available_capital": self.available_capital,
            "current_capital": self.current_capital,
            "holdings": list(self.open_positions.keys()),
            "positions": self.get_positions(),
        }

    def get_account_info(self) -> Dict[str, Any]:
        """Account information and performance metrics."""
        total_value = self.current_capital
        total_return = (total_value - self.initial_capital) / self.initial_capital * 100

        total_closed = len(self.closed_trades)
        win_rate = (self.winning_trades / total_closed * 100) if total_closed > 0 else 0

        if self.closed_trades:
            avg_pnl = sum(t.realized_pnl for t in self.closed_trades) / len(self.closed_trades)
            avg_win = sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl > 0) / self.winning_trades if self.winning_trades > 0 else 0
            avg_loss = sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl < 0) / self.losing_trades if self.losing_trades > 0 else 0
        else:
            avg_pnl = avg_win = avg_loss = 0

        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "available_capital": self.available_capital,
            "total_value": total_value,
            "total_return": total_return,
            "peak_capital": self.peak_capital,
            "max_drawdown": self.max_drawdown * 100,
            "total_trades": self.total_trades,
            "open_positions": len(self.open_positions),
            "closed_trades": total_closed,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "total_commission": self.total_commission,
            "avg_pnl": avg_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }

    def generate_performance_report(self) -> Dict[str, Any]:
        """Detailed performance report (account info + trade-sequence metrics)."""
        return {
            **self.get_account_info(),
            "report_timestamp": datetime.now().isoformat(),
            "trading_days": len(set(t.timestamp[:10] for t in self.all_trades)),
            "best_trade": max((t.realized_pnl for t in self.closed_trades), default=0),
            "worst_trade": min((t.realized_pnl for t in self.closed_trades), default=0),
            "consecutive_wins": self._calculate_consecutive_wins(),
            "consecutive_losses": self._calculate_consecutive_losses(),
            "sharpe_ratio": self._calculate_sharpe_ratio(),
            "profit_factor": self._calculate_profit_factor(),
        }

    def _calculate_consecutive_wins(self) -> int:
        max_wins = current_wins = 0
        for trade in self.closed_trades:
            if trade.realized_pnl > 0:
                current_wins += 1
                max_wins = max(max_wins, current_wins)
            else:
                current_wins = 0
        return max_wins

    def _calculate_consecutive_losses(self) -> int:
        max_losses = current_losses = 0
        for trade in self.closed_trades:
            if trade.realized_pnl < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0
        return max_losses

    def _calculate_sharpe_ratio(self) -> float:
        """Per-trade Sharpe: mean / std of realized per-trade % returns.

        A per-trade (not annualized) ratio computed entirely in percent units. The
        per-trade risk-free rate is negligible at this granularity (a few-day hold),
        so it's omitted rather than mixed in as a fraction against percent returns —
        the old code subtracted a ~3e-6 fraction from percent-scale returns, a unit
        mismatch. Higher = more return per unit of trade-to-trade volatility.
        """
        returns = [t.pnl_percent for t in self.closed_trades]
        if len(returns) < 2:
            return 0.0
        std_return = pd.Series(returns).std()
        if std_return == 0:
            return 0.0
        avg_return = sum(returns) / len(returns)
        return avg_return / std_return

    def _calculate_profit_factor(self) -> float:
        """Gross profit / gross loss."""
        gross_profit = sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl < 0))
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def _log_trade(self, trade: PaperTrade):
        """Append a trade record to the JSON-lines trade log."""
        try:
            with open(self.trade_log_file, 'a') as f:
                f.write(json.dumps(asdict(trade), default=str) + '\n')
        except Exception as e:
            logger.error(f"Error logging trade: {e}")

    def write_state(self, path: Optional[str] = None):
        """Dump a point-in-time account + positions snapshot for the live monitor.

        Overwrites a single JSON file (not appended) so a poller always reads the
        CURRENT state cheaply. Called once per tick by the runners — the one piece
        of live account state that can't be reconstructed from the log stream.
        """
        path = path or os.path.join(os.path.dirname(self.trade_log_file), 'portfolio_state.json')
        try:
            with open(path, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(timespec='seconds'),
                    'account': self.get_account_info(),
                    'positions': self.get_positions(),
                }, f, default=str)
        except Exception as e:
            logger.error(f"Error writing portfolio state: {e}")
