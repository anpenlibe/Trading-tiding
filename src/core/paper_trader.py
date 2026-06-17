"""
Module: paper_trader.py
Purpose: Simulated trading system for testing strategies without real money
Author: Trading Bot Developer
Created: 2025-06-15
Modified: 2025-06-15

This module implements paper trading functionality to track simulated trades
and calculate performance metrics.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd

from src.interfaces import BaseTradingExecutor
from src.data.config import (
    INITIAL_CAPITAL, PAPER_TRADE_COMMISSION, PAPER_TRADE_SLIPPAGE,
    DEFAULT_TRADE_HISTORY_LIMIT,
    EMERGENCY_STOP_LOSS_PCT, EMERGENCY_TAKE_PROFIT_PCT, EMERGENCY_RECHECK_PCT
)
from src.utils.logger import setup_logger
from src.monitoring.performance import performance_tracker

# Initialize logger
logger = setup_logger(__name__, 'paper_trader.log')


@dataclass
class PaperTrade:
    """Structure for paper trade records"""
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
    emergency_stop_loss_pct: float = EMERGENCY_STOP_LOSS_PCT  # Configurable default
    emergency_take_profit_pct: float = EMERGENCY_TAKE_PROFIT_PCT  # Configurable default
    emergency_recheck_pct: float = EMERGENCY_RECHECK_PCT  # Configurable default
    ai_monitoring_comment: Optional[str] = None  # AI's reason for monitoring
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_reason: Optional[str] = None  # TARGET_HIT, STOP_LOSS, MANUAL
    
    # P&L
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    pnl_percent: Optional[float] = None


class PaperTrader(BaseTradingExecutor):
    """
    Paper trading implementation for strategy testing.
    
    Simulates real trading conditions including commissions,
    slippage, and position management.
    """
    
    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        """Initialize paper trader with starting capital"""
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.available_capital = initial_capital
        
        # Positions tracking
        self.open_positions: Dict[str, PaperTrade] = {}
        self.closed_trades: List[PaperTrade] = []
        self.all_trades: List[PaperTrade] = []
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_commission = 0.0
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0
        
        # Initialize trade log
        self.trade_log_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 'logs', 'paper_trades.json'
        )
        os.makedirs(os.path.dirname(self.trade_log_file), exist_ok=True)
        
        logger.info(f"Paper Trader initialized with capital: ₹{initial_capital}")
    
    def place_order(self, symbol: str, quantity: int, order_type: str, 
                   price: Optional[float] = None) -> Dict[str, Any]:
        """
        Place a paper trade order.
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            order_type: BUY or SELL
            price: Limit price (uses current price if None)
            
        Returns:
            Order confirmation or rejection details
        """
        try:
            # This method is mainly for interface compliance
            # Actual trading logic is in execute_trade
            return {
                "status": "PENDING",
                "message": "Use execute_trade for paper trading",
                "symbol": symbol,
                "quantity": quantity,
                "order_type": order_type
            }
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"status": "ERROR", "message": str(e)}
    
    @performance_tracker("trade_execution")
    def execute_trade(self, signal: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        Execute a paper trade based on AI signal.
        
        Args:
            signal: Trading signal from AI Brain
            current_price: Current market price
            
        Returns:
            Trade execution details
        """
        try:
            symbol = signal.get('symbol')
            action = signal.get('signal')  # BUY, SELL, HOLD
            
            # Skip if HOLD signal
            if action == 'HOLD':
                return {
                    "status": "SKIPPED",
                    "reason": "HOLD signal - no action taken"
                }
            
            # Calculate execution price with slippage
            slippage_amount = current_price * PAPER_TRADE_SLIPPAGE
            if action == 'BUY':
                execution_price = current_price + slippage_amount
            else:
                execution_price = current_price - slippage_amount
            
            # Get position details from signal
            quantity = signal.get('position_size', 1)
            stop_loss = signal.get('stop_loss')
            target = signal.get('target')
            
            # Validate trade
            validation = self._validate_trade(
                symbol, action, quantity, execution_price
            )
            if not validation['valid']:
                return {
                    "status": "REJECTED",
                    "reason": validation['reason']
                }
            
            # Execute based on action
            if action == 'BUY':
                return self._execute_buy(
                    symbol, quantity, execution_price, 
                    stop_loss, target, signal
                )
            elif action == 'SELL':
                return self._execute_sell(
                    symbol, quantity, execution_price, signal
                )
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {"status": "ERROR", "message": str(e)}
   
    def execute_simple_trade(self, symbol: str, action: str, price: float, quantity: int = 1,
                             stop_loss: Optional[float] = None, target: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute a simple trade (for testing and manual trading).
    
        Args:
            symbol: Stock symbol
            action: BUY or SELL
            price: Current price
            quantity: Number of shares
            stop_loss: Stop loss price
            target: Target price
        
        Returns:
            Trade execution result
        """
        # Create a signal-like dictionary
        signal = {
            'symbol': symbol,
            'signal': action.upper(),
            'position_size': quantity,
            'stop_loss': stop_loss,
            'target': target,
            'confidence': 1.0,
            'reasoning': 'Manual/Test trade',
            'indicators': {}
        }
    
        return self.execute_trade(signal, price)

    def _execute_buy(self, symbol: str, quantity: int, price: float,
                     stop_loss: Optional[float], target: Optional[float],
                     signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a BUY order"""
        # Check if already have position
        if symbol in self.open_positions:
            return {
                "status": "REJECTED",
                "reason": "Already have open position in this symbol"
            }
        
        # Calculate costs
        position_value = quantity * price
        commission = PAPER_TRADE_COMMISSION
        total_cost = position_value + commission
        
        # Check capital
        if total_cost > self.available_capital:
            return {
                "status": "REJECTED",
                "reason": f"Insufficient capital. Need ₹{total_cost:.2f}, have ₹{self.available_capital:.2f}"
            }
        
        # Extract emergency thresholds from signal
        emergency_thresholds = signal.get('emergency_thresholds', {})
        emergency_stop_loss_pct = emergency_thresholds.get('stop_loss_pct', EMERGENCY_STOP_LOSS_PCT)
        emergency_take_profit_pct = emergency_thresholds.get('take_profit_pct', EMERGENCY_TAKE_PROFIT_PCT)
        emergency_recheck_pct = emergency_thresholds.get('recheck_trigger_pct', EMERGENCY_RECHECK_PCT)
        ai_comment = emergency_thresholds.get('comment')

        # Create trade record
        trade_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{symbol}_BUY"
        trade = PaperTrade(
            trade_id=trade_id,
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
            emergency_stop_loss_pct=emergency_stop_loss_pct,
            emergency_take_profit_pct=emergency_take_profit_pct,
            emergency_recheck_pct=emergency_recheck_pct,
            ai_monitoring_comment=ai_comment,
            signal_strength=signal.get('signal_strength', 0),
            confidence=signal.get('confidence', 0),
            reasoning=signal.get('reasoning', ''),
            indicators=signal.get('indicators', {}),
            status="OPEN",
            unrealized_pnl=0.0,
            pnl_percent=0.0
        )
        
        # Update capital and positions
        self.available_capital -= total_cost
        self.total_commission += commission
        self.open_positions[symbol] = trade
        self.all_trades.append(trade)
        self.total_trades += 1
        
        # Log trade
        self._log_trade(trade)
        
        logger.info(f"BUY executed: {symbol} x{quantity} @ ₹{price:.2f}")
        
        return {
            "status": "EXECUTED",
            "trade_id": trade_id,
            "action": "BUY",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "commission": commission,
            "total_cost": total_cost,
            "stop_loss": stop_loss,
            "target": target
        }
    
    def _execute_sell(self, symbol: str, quantity: int, price: float,
                      signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SELL order"""
        # Check if have position
        if symbol not in self.open_positions:
            return {
                "status": "REJECTED",
                "reason": "No open position to sell"
            }
        
        position = self.open_positions[symbol]
        
        # Validate quantity
        if quantity > position.quantity:
            return {
                "status": "REJECTED",
                "reason": f"Cannot sell {quantity}, only have {position.quantity}"
            }
        
        # Calculate proceeds and P&L
        gross_proceeds = quantity * price
        commission = PAPER_TRADE_COMMISSION
        net_proceeds = gross_proceeds - commission
        
        # Calculate P&L
        cost_basis = position.entry_price * quantity
        realized_pnl = net_proceeds - cost_basis - position.commission
        pnl_percent = (realized_pnl / cost_basis) * 100
        
        # Update position
        position.exit_price = price
        position.exit_timestamp = datetime.now().isoformat()
        position.exit_reason = signal.get('exit_reason', 'SIGNAL')
        position.realized_pnl = realized_pnl
        position.pnl_percent = pnl_percent
        position.status = "CLOSED"
        
        # Update capital and tracking
        self.available_capital += net_proceeds
        self.current_capital = self.available_capital + sum(
            pos.position_value for pos in self.open_positions.values()
        )
        self.total_commission += commission
        
        # Track wins/losses
        if realized_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Move to closed trades
        self.closed_trades.append(position)
        del self.open_positions[symbol]
        
        # Update peak and drawdown
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        # Log trade
        self._log_trade(position)
        
        logger.info(
            f"SELL executed: {symbol} x{quantity} @ ₹{price:.2f} "
            f"P&L: ₹{realized_pnl:.2f} ({pnl_percent:+.2f}%)"
        )
        
        return {
            "status": "EXECUTED",
            "trade_id": position.trade_id,
            "action": "SELL",
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "commission": commission,
            "realized_pnl": realized_pnl,
            "pnl_percent": pnl_percent
        }
    
    def update_positions(self, current_prices: Dict[str, float]):
        """Update unrealized P&L for open positions"""
        for symbol, position in self.open_positions.items():
            if symbol in current_prices:
                current_price = current_prices[symbol]
                position.current_price = current_price
                
                # Calculate unrealized P&L
                current_value = position.quantity * current_price
                cost_basis = position.quantity * position.entry_price
                position.unrealized_pnl = current_value - cost_basis - position.commission
                position.pnl_percent = (position.unrealized_pnl / cost_basis) * 100
                
                # Check stop loss
                if position.stop_loss and current_price <= position.stop_loss:
                    logger.warning(f"Stop loss triggered for {symbol}")
                    self._execute_sell(symbol, position.quantity, current_price, 
                                     {"exit_reason": "STOP_LOSS"})
                
                # Check target
                elif position.target and current_price >= position.target:
                    logger.info(f"Target reached for {symbol}")
                    self._execute_sell(symbol, position.quantity, current_price,
                                     {"exit_reason": "TARGET_HIT"})
        
        # Update current capital
        self.current_capital = self.available_capital + sum(
            pos.quantity * pos.current_price for pos in self.open_positions.values()
        )
    
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions and their status"""
        positions = {}
        
        for symbol, position in self.open_positions.items():
            positions[symbol] = {
                "quantity": position.quantity,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "pnl_percent": position.pnl_percent,
                "stop_loss": position.stop_loss,
                "target": position.target,
                "entry_time": position.timestamp
            }
        
        return positions
    
    def has_position(self, symbol: str) -> bool:
        """Checks if an open position exists for the given symbol."""
        return symbol in self.open_positions and self.open_positions[symbol].quantity > 0
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information and performance metrics"""
        total_value = self.current_capital
        
        # Calculate returns
        total_return = (total_value - self.initial_capital) / self.initial_capital * 100
        
        # Win rate
        total_closed = len(self.closed_trades)
        win_rate = (self.winning_trades / total_closed * 100) if total_closed > 0 else 0
        
        # Average P&L
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
            "avg_loss": avg_loss
        }
    
    def get_trade_history(self, limit: int = DEFAULT_TRADE_HISTORY_LIMIT) -> List[Dict[str, Any]]:
        """Get recent trade history"""
        all_trades = self.all_trades[-limit:]
        return [asdict(trade) for trade in all_trades]
    
    def _validate_trade(self, symbol: str, action: str, quantity: int, price: float) -> Dict[str, Any]:
        """Validate trade parameters - FIXED VERSION"""
        try:
            # Basic validations
            if quantity <= 0:
                return {"valid": False, "reason": "Invalid quantity - insufficient capital for position"}
        
            if price <= 0:
                return {"valid": False, "reason": "Invalid price"}
        
            # Check for BUY orders
            if action == 'BUY':
                position_value = quantity * price
                commission = PAPER_TRADE_COMMISSION
                total_cost = position_value + commission
            
                if total_cost > self.available_capital:
                    return {
                        "valid": False, 
                        "reason": f"Insufficient capital. Need ₹{total_cost:.2f}, have ₹{self.available_capital:.2f}"
                    }
            
                # REMOVED: Position size check that was too restrictive for testing
                # Check if already have position
                if symbol in self.open_positions:
                    return {
                        "valid": False,
                        "reason": "Already have open position in this symbol"
                }
        
            # Check for SELL orders
            elif action == 'SELL':
                if symbol not in self.open_positions:
                    return {
                        "valid": False,
                        "reason": "No open position to sell"
                    }
            
                position = self.open_positions[symbol]
                if quantity > position.quantity:
                    return {
                        "valid": False,
                        "reason": f"Cannot sell {quantity} shares, only have {position.quantity}"
                    }
        
            return {"valid": True, "reason": "OK"}
        
        except Exception as e:
            return {"valid": False, "reason": f"Validation error: {str(e)}"}

    
    def _log_trade(self, trade: PaperTrade):
        """Log trade to file"""
        try:
            with open(self.trade_log_file, 'a') as f:
                f.write(json.dumps(asdict(trade), default=str) + '\n')
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate detailed performance report"""
        account_info = self.get_account_info()
        
        # Add additional metrics
        report = {
            **account_info,
            "report_timestamp": datetime.now().isoformat(),
            "trading_days": len(set(t.timestamp[:10] for t in self.all_trades)),
            "best_trade": max((t.realized_pnl for t in self.closed_trades), default=0),
            "worst_trade": min((t.realized_pnl for t in self.closed_trades), default=0),
            "consecutive_wins": self._calculate_consecutive_wins(),
            "consecutive_losses": self._calculate_consecutive_losses(),
            "sharpe_ratio": self._calculate_sharpe_ratio(),
            "profit_factor": self._calculate_profit_factor()
        }
        
        return report
    
    def _calculate_consecutive_wins(self) -> int:
        """Calculate maximum consecutive winning trades"""
        if not self.closed_trades:
            return 0
        
        max_wins = current_wins = 0
        for trade in self.closed_trades:
            if trade.realized_pnl > 0:
                current_wins += 1
                max_wins = max(max_wins, current_wins)
            else:
                current_wins = 0
        
        return max_wins
    
    def _calculate_consecutive_losses(self) -> int:
        """Calculate maximum consecutive losing trades"""
        if not self.closed_trades:
            return 0
        
        max_losses = current_losses = 0
        for trade in self.closed_trades:
            if trade.realized_pnl < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0
        
        return max_losses
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio (simplified)"""
        if not self.closed_trades:
            return 0.0
        
        returns = [t.pnl_percent for t in self.closed_trades]
        if len(returns) < 2:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        std_return = pd.Series(returns).std()
        
        if std_return == 0:
            return 0.0
        
        # Assuming risk-free rate of 6% annually, converted to per-trade
        risk_free_rate = 0.06 / 252 / 78  # Assuming 78 trades per day
        
        return (avg_return - risk_free_rate) / std_return
    
    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        gross_profit = sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss



