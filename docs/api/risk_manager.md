# risk_manager

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

## Class: `RiskParameters`

Container for risk calculation results

## Class: `SimpleRiskManager`

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

### Methods

#### `__init__(self, risk_per_trade, stop_loss_percent, take_profit_percent, commission, slippage)`

Initialize risk manager with customizable parameters.

Args:
    risk_per_trade: Maximum risk per trade as decimal (0.02 = 2%)
    stop_loss_percent: Default stop loss distance as decimal
    take_profit_percent: Default target distance as decimal
    commission: Fixed commission per trade
    slippage: Expected slippage as decimal

#### `calculate_position_size(self, capital, risk_per_trade, stop_loss_distance)`

Calculate position size based on risk parameters.

This is the core Kelly Criterion-inspired position sizing:
Position Size = Risk Amount / Risk per Share

Args:
    capital: Total available capital
    risk_per_trade: Risk percentage as decimal (0.02 = 2%)
    stop_loss_distance: Dollar distance to stop loss
    
Returns:
    Number of shares to trade

#### `calculate_risk_parameters(self, symbol, signal_type, entry_price, capital, stop_loss, target, custom_risk_percent)`

Calculate comprehensive risk parameters for a trade.

Args:
    symbol: Trading symbol
    signal_type: BUY or SELL
    entry_price: Intended entry price
    capital: Available capital
    stop_loss: Optional custom stop loss
    target: Optional custom target
    custom_risk_percent: Optional custom risk percentage
    
Returns:
    RiskParameters object with all calculations

#### `validate_trade(self, signal, current_positions)`

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

#### `calculate_portfolio_risk(self, positions, current_prices)`

Calculate overall portfolio risk metrics.

Future enhancement: Add correlation-based risk calculations

Args:
    positions: Current open positions
    current_prices: Current market prices
    
Returns:
    Dict with portfolio risk metrics

#### `suggest_position_adjustment(self, symbol, current_price, position, market_conditions)`

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

## Functions

### `__init__(self, risk_per_trade, stop_loss_percent, take_profit_percent, commission, slippage)`

Initialize risk manager with customizable parameters.

Args:
    risk_per_trade: Maximum risk per trade as decimal (0.02 = 2%)
    stop_loss_percent: Default stop loss distance as decimal
    take_profit_percent: Default target distance as decimal
    commission: Fixed commission per trade
    slippage: Expected slippage as decimal

### `calculate_position_size(self, capital, risk_per_trade, stop_loss_distance)`

Calculate position size based on risk parameters.

This is the core Kelly Criterion-inspired position sizing:
Position Size = Risk Amount / Risk per Share

Args:
    capital: Total available capital
    risk_per_trade: Risk percentage as decimal (0.02 = 2%)
    stop_loss_distance: Dollar distance to stop loss
    
Returns:
    Number of shares to trade

### `calculate_risk_parameters(self, symbol, signal_type, entry_price, capital, stop_loss, target, custom_risk_percent)`

Calculate comprehensive risk parameters for a trade.

Args:
    symbol: Trading symbol
    signal_type: BUY or SELL
    entry_price: Intended entry price
    capital: Available capital
    stop_loss: Optional custom stop loss
    target: Optional custom target
    custom_risk_percent: Optional custom risk percentage
    
Returns:
    RiskParameters object with all calculations

### `validate_trade(self, signal, current_positions)`

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

### `calculate_portfolio_risk(self, positions, current_prices)`

Calculate overall portfolio risk metrics.

Future enhancement: Add correlation-based risk calculations

Args:
    positions: Current open positions
    current_prices: Current market prices
    
Returns:
    Dict with portfolio risk metrics

### `suggest_position_adjustment(self, symbol, current_price, position, market_conditions)`

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

