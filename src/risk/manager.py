"""
Module: risk_manager.py
Purpose: Centralized risk management for trading operations
Author: Trading Bot Developer
Created: 2025-06-15
Modified: 2025-06-15

This module implements risk management logic including:
- Position sizing based on risk parameters
- Stop loss and target calculation
- Trade validation
- Commission and slippage handling
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

from src.platform.types import BaseRiskManager
from src.platform.config import (
    MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT,
    PAPER_TRADE_COMMISSION, PAPER_TRADE_SLIPPAGE,
    MIN_TRADE_VALUE, MAX_POSITION_SIZE
)

# Set up logger
logger = logging.getLogger(__name__)


@dataclass
class RiskParameters:
    """Container for risk calculation results"""
    position_size: int
    risk_amount: float
    stop_loss: float
    target: float
    entry_price: float
    commission: float
    total_cost: float
    risk_reward_ratio: float
    position_value: float
    max_loss: float


class SimpleRiskManager(BaseRiskManager):
    """
    Simple risk manager implementing fixed percentage risk per trade.
    
    Features:
    - Fixed risk per trade (default 2% of capital)
    - Automatic stop loss calculation
    - Position sizing based on stop distance
    - Commission and slippage handling
    
    Future extensions:
    - ATR-based dynamic stop loss
    - Volatility-adjusted position sizing
    - Correlation-based portfolio risk
    - Time-based risk adjustments
    """
    
    def __init__(self, 
                 risk_per_trade: float = MAX_RISK_PER_TRADE,
                 stop_loss_percent: float = STOP_LOSS_PERCENT,
                 take_profit_percent: float = TAKE_PROFIT_PERCENT,
                 commission: float = PAPER_TRADE_COMMISSION,
                 slippage: float = PAPER_TRADE_SLIPPAGE):
        """
        Initialize risk manager with customizable parameters.
        
        Args:
            risk_per_trade: Maximum risk per trade as decimal (0.02 = 2%)
            stop_loss_percent: Default stop loss distance as decimal
            take_profit_percent: Default target distance as decimal
            commission: Fixed commission per trade
            slippage: Expected slippage as decimal
        """
        self.risk_per_trade = risk_per_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.commission = commission
        self.slippage = slippage
        
        # Validate risk-reward ratio
        self.risk_reward_ratio = self.take_profit_percent / self.stop_loss_percent
        if self.risk_reward_ratio < 1.5:
            logger.warning(f"Risk-reward ratio {self.risk_reward_ratio:.1f} is below recommended 1.5")
    
    def calculate_position_size(self, capital: float, risk_per_trade: float,
                              stop_loss_distance: float, entry_price: float = None) -> int:
        """
        Calculate position size with CAPITAL-FIRST approach to respect position limits.

        NEW ALGORITHM:
        1. Calculate max position value based on capital limits
        2. Calculate Kelly-suggested position size
        3. Take the MINIMUM to respect both risk and capital constraints

        Args:
            capital: Total available capital
            risk_per_trade: Risk percentage as decimal (0.02 = 2%)
            stop_loss_distance: Dollar distance to stop loss
            entry_price: Entry price for position value calculation

        Returns:
            Number of shares to trade (respects both risk and capital limits)
        """
        if stop_loss_distance <= 0:
            logger.error("Stop loss distance must be positive")
            return 0

        # Calculate Kelly-suggested position size (old method)
        risk_amount = capital * risk_per_trade
        kelly_position_size = int(risk_amount / stop_loss_distance)

        # NEW: Calculate maximum position size based on capital limits
        if entry_price and entry_price > 0:
            max_position_value = capital * MAX_POSITION_SIZE  # 20% of capital
            max_shares_by_capital = int(max_position_value / entry_price)

            # Take the MINIMUM to respect both constraints
            position_size = min(kelly_position_size, max_shares_by_capital)

            # Calculate actual values for logging
            actual_position_value = position_size * entry_price
            actual_position_percent = (actual_position_value / capital) * 100
            actual_risk = position_size * stop_loss_distance
            actual_risk_percent = (actual_risk / capital) * 100

            logger.debug(f"Position sizing: Capital=₹{capital:,.0f}, Target Risk={risk_per_trade*100:.1f}%")
            logger.debug(f"  Kelly suggests: {kelly_position_size} shares")
            logger.debug(f"  Capital limits: {max_shares_by_capital} shares (max {MAX_POSITION_SIZE*100}%)")
            logger.debug(f"  Final position: {position_size} shares = ₹{actual_position_value:,.0f} ({actual_position_percent:.1f}%)")
            logger.debug(f"  Actual risk: ₹{actual_risk:,.0f} ({actual_risk_percent:.1f}%)")

        else:
            # Fallback to Kelly method if no entry price provided
            position_size = kelly_position_size
            logger.warning("No entry_price provided - using Kelly method only (may violate position limits)")

        # Ensure at least 1 share, but only if it doesn't violate capital limits
        if entry_price and entry_price > 0:
            if entry_price <= capital * MAX_POSITION_SIZE:  # 1 share fits in position limit
                position_size = max(1, position_size)
            else:
                position_size = 0  # Even 1 share exceeds position limits
                logger.warning(
                    f"Stock price ₹{entry_price:,.0f} exceeds capital "
                    f"position limit of ₹{capital * MAX_POSITION_SIZE:,.0f}"
                )
        else:
            position_size = max(1, position_size)

        return position_size
    
    def calculate_risk_parameters(self,
                                symbol: str,
                                signal_type: str,  # BUY or SELL
                                entry_price: float,
                                capital: float,
                                stop_loss: Optional[float] = None,
                                target: Optional[float] = None,
                                custom_risk_percent: Optional[float] = None,
                                atr: Optional[float] = None,
                                atr_mult: float = 2.0,
                                atr_target_mult: float = 3.0) -> RiskParameters:
        """
        Calculate comprehensive risk parameters for a trade.

        Args:
            symbol: Trading symbol
            signal_type: BUY or SELL
            entry_price: Intended entry price
            capital: Available capital
            stop_loss: Optional custom stop loss
            target: Optional custom target
            custom_risk_percent: Optional custom risk percentage
            atr: Optional ATR(14) for the symbol — when given (and no explicit
                stop/target), stops/targets scale with the stock's own volatility
                (stop = entry ∓ atr_mult*ATR) instead of a flat percentage, so a
                volatile name gets a wider stop and a quiet one a tighter stop.
            atr_mult: ATR multiple for the stop distance (default 2.0)
            atr_target_mult: ATR multiple for the target distance (default 3.0,
                keeping the 1.5:1 reward:risk the % defaults also use)

        Returns:
            RiskParameters object with all calculations
        """
        # Use custom risk or default
        risk_percent = custom_risk_percent or self.risk_per_trade

        # Volatility-based stop distance when ATR is available; else fixed percent.
        use_atr = atr is not None and atr > 0
        stop_dist = atr * atr_mult if use_atr else None
        target_dist = atr * atr_target_mult if use_atr else None

        # Adjust entry price for slippage
        if signal_type == "BUY":
            adjusted_entry = entry_price * (1 + self.slippage)
            if stop_loss is None:
                stop_loss = (entry_price - stop_dist) if use_atr else entry_price * (1 - self.stop_loss_percent)
            if target is None:
                target = (entry_price + target_dist) if use_atr else entry_price * (1 + self.take_profit_percent)
        else:  # SELL
            adjusted_entry = entry_price * (1 - self.slippage)
            if stop_loss is None:
                stop_loss = (entry_price + stop_dist) if use_atr else entry_price * (1 + self.stop_loss_percent)
            if target is None:
                target = (entry_price - target_dist) if use_atr else entry_price * (1 - self.take_profit_percent)
        
        # Calculate stop distance
        stop_distance = abs(adjusted_entry - stop_loss)
        
        # Calculate position size
        position_size = self.calculate_position_size(capital, risk_percent, stop_distance, adjusted_entry)
        
        # Calculate position value and costs
        position_value = position_size * adjusted_entry
        total_cost = position_value + self.commission
        
        # Ensure we don't exceed capital
        if total_cost > capital:
            # Reduce position size to fit capital
            max_position_size = int((capital - self.commission) / adjusted_entry)
            position_size = max(1, min(position_size, max_position_size))
            position_value = position_size * adjusted_entry
            total_cost = position_value + self.commission
        
        # Recalculate actual risk
        actual_risk = position_size * stop_distance
        max_loss = actual_risk + self.commission
        
        # Calculate risk-reward ratio
        target_distance = abs(target - adjusted_entry)
        actual_rr_ratio = target_distance / stop_distance if stop_distance > 0 else 0
        
        return RiskParameters(
            position_size=position_size,
            risk_amount=actual_risk,
            stop_loss=stop_loss,
            target=target,
            entry_price=adjusted_entry,
            commission=self.commission,
            total_cost=total_cost,
            risk_reward_ratio=actual_rr_ratio,
            position_value=position_value,
            max_loss=max_loss
        )
    
    def validate_trade(self, signal: Dict[str, Any], 
                      current_positions: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate if a trade should be taken based on risk rules.
        
        Validation checks:
        1. Sufficient capital
        2. Position size limits
        3. Maximum positions
        4. Risk-reward ratio
        5. Minimum trade value
        
        Args:
            signal: Trading signal with symbol, price, etc.
            current_positions: Current open positions
            
        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        symbol = signal.get('symbol')
        signal_type = signal.get('signal', 'BUY')
        entry_price = signal.get('entry_price', signal.get('price'))
        available_capital = signal.get('available_capital', 0)

        # A SELL closes an existing position. The capital / position-size /
        # "already hold this symbol" checks below are all for OPENING (BUY);
        # applying them to a SELL would reject every exit. The executor
        # (_execute_sell) validates that a position actually exists.
        if signal_type == 'SELL':
            return True, None

        # A BUY needs a price to size the position. Bail cleanly instead of
        # crashing on `None * slippage` downstream (which callers swallow as a
        # silent non-execution).
        if entry_price is None:
            return False, "No entry price provided for trade"

        # Check if we already have a position in this symbol
        if symbol in current_positions:
            return False, f"Already have open position in {symbol}"
        
        # Check minimum capital
        if available_capital < MIN_TRADE_VALUE:
            return False, f"Insufficient capital: ₹{available_capital:.2f} < ₹{MIN_TRADE_VALUE}"

        # Capital-adaptive affordability gate: a single share priced above the
        # per-position cap (capital × MAX_POSITION_SIZE) can't be held within risk
        # limits at this capital, so position sizing returns 0 shares. Report that
        # honestly and short-circuit BEFORE sizing — otherwise it falls through to
        # the generic "trade value ₹0.00 below minimum" message below, which blames
        # capital rather than the stock's price. This is how the tradeable universe
        # adapts to capital: the cap is fixed, expensive names drop out when capital
        # is small and reappear as it grows.
        max_position_value = available_capital * MAX_POSITION_SIZE
        if entry_price > max_position_value:
            return False, (
                f"{symbol} @ ₹{entry_price:,.0f} exceeds max position "
                f"₹{max_position_value:,.0f} ({MAX_POSITION_SIZE*100:.0f}% of ₹{available_capital:,.0f})"
            )

        # Calculate risk parameters
        risk_params = self.calculate_risk_parameters(
            symbol=symbol,
            signal_type=signal.get('signal', 'BUY'),
            entry_price=entry_price,
            capital=available_capital,
            stop_loss=signal.get('stop_loss'),
            target=signal.get('target')
        )
        
        # Check if trade value meets minimum
        if risk_params.position_value < MIN_TRADE_VALUE:
            return False, f"Trade value ₹{risk_params.position_value:.2f} below minimum ₹{MIN_TRADE_VALUE}"
        
        # Check if position size exceeds maximum allowed
        if risk_params.position_value > available_capital * MAX_POSITION_SIZE:
            return False, f"Position size exceeds {MAX_POSITION_SIZE*100}% of capital"
        
        # Check risk-reward ratio
        if risk_params.risk_reward_ratio < 1.5:
            return False, f"Risk-reward ratio {risk_params.risk_reward_ratio:.1f} below minimum 1.5"
        
        # Check if we can afford the trade
        if risk_params.total_cost > available_capital:
            return False, f"Total cost ₹{risk_params.total_cost:.2f} exceeds available capital ₹{available_capital:.2f}"
        
        # All checks passed
        return True, None
    
    def calculate_portfolio_risk(self, positions: Dict[str, Any], 
                               current_prices: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate overall portfolio risk metrics.
        
        Future enhancement: Add correlation-based risk calculations
        
        Args:
            positions: Current open positions
            current_prices: Current market prices
            
        Returns:
            Dict with portfolio risk metrics
        """
        total_risk = 0
        total_value = 0
        
        for symbol, position in positions.items():
            current_price = current_prices.get(symbol, position.get('entry_price', 0))
            position_value = position.get('quantity', 0) * current_price
            
            # Calculate risk based on stop loss
            if position.get('stop_loss'):
                stop_distance = abs(current_price - position['stop_loss'])
                position_risk = position['quantity'] * stop_distance
                total_risk += position_risk
            
            total_value += position_value
        
        return {
            'total_portfolio_value': total_value,
            'total_risk_amount': total_risk,
            'number_of_positions': len(positions),
            'average_position_size': total_value / len(positions) if positions else 0
        }
    
    def suggest_position_adjustment(self, 
                                  symbol: str,
                                  current_price: float,
                                  position: Dict[str, Any],
                                  market_conditions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Suggest position adjustments based on price movement.
        
        Future enhancements:
        - Trailing stop loss based on ATR
        - Partial profit taking
        - Position scaling
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            position: Current position details
            market_conditions: Optional market indicators (volatility, trend, etc.)
            
        Returns:
            Suggested adjustments
        """
        entry_price = position.get('entry_price', position.get('avg_price'))
        current_stop = position.get('stop_loss')
        is_profitable = current_price > entry_price if position.get('side') == 'LONG' else current_price < entry_price
        
        suggestions = {
            'adjust_stop_loss': False,
            'new_stop_loss': current_stop,
            'take_partial_profit': False,
            'add_to_position': False,
            'close_position': False,
            'reasoning': []
        }
        
        if is_profitable:
            # Calculate profit percentage
            profit_pct = abs(current_price - entry_price) / entry_price
            
            # Suggest trailing stop if profit > 2%
            if profit_pct > 0.02:
                if position.get('side') == 'LONG':
                    new_stop = current_price * (1 - self.stop_loss_percent * 0.5)  # Tighter stop
                    if new_stop > current_stop:
                        suggestions['adjust_stop_loss'] = True
                        suggestions['new_stop_loss'] = new_stop
                        suggestions['reasoning'].append(f"Trail stop to ₹{new_stop:.2f} to lock in profits")
            
            # Suggest partial profit if profit > 4%
            if profit_pct > 0.04:
                suggestions['take_partial_profit'] = True
                suggestions['reasoning'].append("Consider taking 50% profit at 4%+ gain")
        
        return suggestions

