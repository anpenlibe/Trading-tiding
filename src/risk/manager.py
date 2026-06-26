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
    PAPER_TRADE_COMMISSION, PAPER_TRADE_SLIPPAGE, TRADING_PRODUCT,
    MIN_TRADE_VALUE, MAX_POSITION_SIZE,
    MIN_ACT_CONFIDENCE, CONVICTION_RISK_FLOOR_FRAC,
)
from src.execution.costs import compute_charges

# Set up logger
logger = logging.getLogger(__name__)


def conviction_risk_percent(confidence: float,
                            max_risk: float = MAX_RISK_PER_TRADE,
                            floor_frac: float = CONVICTION_RISK_FLOOR_FRAC,
                            min_conf: float = MIN_ACT_CONFIDENCE) -> float:
    """Map confidence to the fraction of capital to risk — conviction sizing.

    Linearly interpolates confidence in [min_conf, 1.0] to a risk fraction in
    [floor_frac*max_risk, max_risk]: a just-above-floor entry takes a starter-sized
    position, a full-conviction entry leans up to the cap. Clamped both ends (a
    confidence below the floor — which the pipeline floor gate normally skips — still
    never returns below floor_frac; above 1.0 returns max_risk), so it is safe even if
    called directly. The hard cap MAX_RISK_PER_TRADE is never exceeded."""
    c = max(min_conf, min(1.0, confidence))
    if min_conf >= 1.0:                       # degenerate config guard (no divide-by-0)
        return max_risk
    t = (c - min_conf) / (1.0 - min_conf)     # 0 at floor, 1 at full conviction
    return max_risk * (floor_frac + (1.0 - floor_frac) * t)


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
            atr_target_mult: ATR multiple for the target distance (default 3.0, a
                3:2 = 1.5:1 reward:risk. Note the % defaults give 2:1
                (TAKE_PROFIT_PERCENT 3% / STOP_LOSS_PERCENT 1.5%); both clear the
                1.5 minimum gate.)

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
        
        # Calculate position value and costs. Use the SAME turnover-based charge
        # model the executor actually bills (execution/costs.compute_charges) plus
        # the optional flat fee, so affordability here matches the real fill — a
        # flat commission of 0 used to let a BUY pass risk then cost more at fill.
        def _charge(value):
            return compute_charges(value, "BUY", TRADING_PRODUCT) + self.commission

        position_value = position_size * adjusted_entry
        total_cost = position_value + _charge(position_value)

        # Ensure we don't exceed capital
        if total_cost > capital:
            # Reduce position size to fit capital (reserve ~1% for charges, then
            # confirm against the real charge on the reduced size).
            max_position_size = int((capital * 0.99) / adjusted_entry)
            position_size = max(1, min(position_size, max_position_size))
            position_value = position_size * adjusted_entry
            total_cost = position_value + _charge(position_value)

        commission = _charge(position_value)

        # Recalculate actual risk
        actual_risk = position_size * stop_distance
        max_loss = actual_risk + commission
        
        # Reward:risk is a GEOMETRY ratio of the stop/target around the INTENDED
        # entry — not the slippage-adjusted entry. Slippage is a cost (it already
        # widens stop_distance for sizing above and feeds total_cost); folding it
        # into this ratio shaved the ATR design's clean 3:2 = 1.50 down to ~1.47,
        # which would trip a `>= 1.5` gate on every ATR trade. Use the raw entry so
        # the ratio reflects the setup the trade is actually designed around.
        rr_stop = abs(entry_price - stop_loss)
        rr_target = abs(target - entry_price)
        actual_rr_ratio = rr_target / rr_stop if rr_stop > 0 else 0
        
        return RiskParameters(
            position_size=position_size,
            risk_amount=actual_risk,
            stop_loss=stop_loss,
            target=target,
            entry_price=adjusted_entry,
            commission=commission,
            total_cost=total_cost,
            risk_reward_ratio=actual_rr_ratio,
            position_value=position_value,
            max_loss=max_loss
        )
    
    def validate_trade(self, signal: Dict[str, Any],
                      current_positions: Dict[str, Any],
                      atr: Optional[float] = None) -> Tuple[bool, Optional[str], Optional[RiskParameters]]:
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
            atr: The symbol's ATR(14) when available. Passed so validation sizes
                and gates the SAME trade execution will place — when ATR is present
                the pipeline lets it set volatility-scaled stops/targets (overriding
                the AI's templated levels), so affordability and reward:risk here
                must be computed against the ATR levels, not the fixed-% template.

        Returns:
            Tuple of (is_valid, rejection_reason, risk_params). risk_params is the
            computed sizing/levels for an accepted BUY (None for a SELL or any
            rejection), so the caller can execute it without recomputing.
        """
        symbol = signal.get('symbol')
        signal_type = signal.get('signal', 'BUY')
        entry_price = signal.get('entry_price', signal.get('price'))
        available_capital = signal.get('available_capital', 0)

        # Per-verb routing. SELL/TRIM/MOVE_STOP act on an EXISTING position and need no
        # sizing; ADD sizes an INCREMENT against the AGGREGATE cap; only BUY opens fresh.
        # A SELL is a full close — the executor validates the holding and sizes the exit.
        if signal_type == 'SELL':
            return True, None, None
        if signal_type in ('TRIM', 'MOVE_STOP'):
            if symbol not in current_positions:
                return False, f"No position in {symbol} to {signal_type}", None
            return True, None, None
        if signal_type == 'ADD':
            return self._validate_add(signal, current_positions, atr)

        # ----- BUY (open a new position) -----
        # A BUY needs a price to size the position. Bail cleanly instead of
        # crashing on `None * slippage` downstream (which callers swallow as a
        # silent non-execution).
        if entry_price is None:
            return False, "No entry price provided for trade", None

        # A BUY opens fresh — adding to a held symbol is ADD's job, not BUY's.
        if symbol in current_positions:
            return False, f"Already have open position in {symbol}", None

        # Check minimum capital
        if available_capital < MIN_TRADE_VALUE:
            return False, f"Insufficient capital: ₹{available_capital:.2f} < ₹{MIN_TRADE_VALUE}", None

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
            ), None

        # Calculate risk parameters for the SAME trade execution will place: when
        # ATR is available it sets the stops/targets (the AI's templated levels are
        # ignored downstream), so pass it through and drop the templated levels.
        # Conviction sizes the trade: confidence scales risk_per_trade within the cap.
        risk_params = self.calculate_risk_parameters(
            symbol=symbol,
            signal_type=signal.get('signal', 'BUY'),
            entry_price=entry_price,
            capital=available_capital,
            stop_loss=None if atr else signal.get('stop_loss'),
            target=None if atr else signal.get('target'),
            custom_risk_percent=conviction_risk_percent(signal.get('confidence', MIN_ACT_CONFIDENCE)),
            atr=atr,
        )
        
        # Check if trade value meets minimum
        if risk_params.position_value < MIN_TRADE_VALUE:
            return False, f"Trade value ₹{risk_params.position_value:.2f} below minimum ₹{MIN_TRADE_VALUE}", None

        # Check if position size exceeds maximum allowed
        if risk_params.position_value > available_capital * MAX_POSITION_SIZE:
            return False, f"Position size exceeds {MAX_POSITION_SIZE*100}% of capital", None

        # Check risk-reward ratio (allow ±0.001 float tolerance — the ATR geometry
        # 3·ATR / 2·ATR lands at 1.4999999…8 for many real prices in IEEE 754, which
        # a strict `< 1.5` would wrongly reject; the error is ~1e-15, far below 1e-3).
        if risk_params.risk_reward_ratio < 1.5 - 1e-3:
            return False, f"Risk-reward ratio {risk_params.risk_reward_ratio:.2f} below minimum 1.5", None

        # Check if we can afford the trade
        if risk_params.total_cost > available_capital:
            return False, f"Total cost ₹{risk_params.total_cost:.2f} exceeds available capital ₹{available_capital:.2f}", None

        # All checks passed — hand back the params so the caller executes exactly
        # what was validated (no second calculate_risk_parameters call).
        return True, None, risk_params

    def _validate_add(self, signal: Dict[str, Any], current_positions: Dict[str, Any],
                      atr: Optional[float] = None) -> Tuple[bool, Optional[str], Optional[RiskParameters]]:
        """Size an ADD (scale-in) increment and gate it on the AGGREGATE position cap.

        The increment is sized exactly like a BUY (ATR-scaled, capital-first), then
        clamped so held_value + increment stays within MAX_POSITION_SIZE of capital — the
        per-position cap is on the COMBINED holding, not each tranche. Returns risk_params
        carrying the (possibly clamped) increment size for the pipeline to stamp on, just
        like a BUY. The executor re-checks affordability as the final floor.
        """
        symbol = signal.get('symbol')
        entry_price = signal.get('entry_price', signal.get('price'))
        available_capital = signal.get('available_capital', 0)

        if symbol not in current_positions:
            return False, f"No position in {symbol} to ADD to", None
        if entry_price is None:
            return False, "No entry price provided for ADD", None

        existing = current_positions[symbol]
        held_value = existing.get('quantity', 0) * existing.get('entry_price', entry_price)
        cap_room = available_capital * MAX_POSITION_SIZE - held_value
        if cap_room <= 0:
            return False, f"{symbol} already at {MAX_POSITION_SIZE*100:.0f}% position cap", None

        # Size the increment like a fresh BUY (ATR sets stops/levels downstream),
        # conviction-scaled by the ADD's own confidence — then aggregate-capped below.
        risk_params = self.calculate_risk_parameters(
            symbol=symbol, signal_type='BUY', entry_price=entry_price,
            capital=available_capital,
            stop_loss=None if atr else signal.get('stop_loss'),
            target=None if atr else signal.get('target'),
            custom_risk_percent=conviction_risk_percent(signal.get('confidence', MIN_ACT_CONFIDENCE)),
            atr=atr,
        )

        # Clamp the increment to the aggregate cap room.
        sized_qty = risk_params.position_size
        agg_room_qty = int(cap_room / risk_params.entry_price)
        final_qty = min(sized_qty, agg_room_qty)
        if final_qty < 1:
            return False, f"{symbol} aggregate position at {MAX_POSITION_SIZE*100:.0f}% cap", None

        final_value = final_qty * risk_params.entry_price
        if final_value < MIN_TRADE_VALUE:
            return False, f"ADD increment ₹{final_value:.2f} below minimum ₹{MIN_TRADE_VALUE}", None

        total_cost = final_value + compute_charges(final_value, "BUY", TRADING_PRODUCT) + self.commission
        if total_cost > available_capital:
            return False, f"ADD cost ₹{total_cost:.2f} exceeds available capital ₹{available_capital:.2f}", None

        # The pipeline reads position_size + risk_amount off risk_params; keep them
        # consistent with the clamped increment (other fields the executor recomputes).
        if final_qty != sized_qty and sized_qty > 0:
            risk_params.risk_amount = risk_params.risk_amount * final_qty / sized_qty
            risk_params.position_size = final_qty
        return True, None, risk_params

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
    
