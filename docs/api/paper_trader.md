# paper_trader

Module: paper_trader.py
Purpose: Simulated trading system for testing strategies without real money
Author: Trading Bot Developer
Created: 2025-06-15
Modified: 2025-06-15

This module implements paper trading functionality to track simulated trades
and calculate performance metrics.

## Class: `PaperTrade`

Structure for paper trade records

## Class: `PaperTrader`

Paper trading implementation for strategy testing.

Simulates real trading conditions including commissions,
slippage, and position management.

### Methods

#### `__init__(self, initial_capital)`

Initialize paper trader with starting capital

#### `place_order(self, symbol, quantity, order_type, price)`

Place a paper trade order.

Args:
    symbol: Stock symbol
    quantity: Number of shares
    order_type: BUY or SELL
    price: Limit price (uses current price if None)
    
Returns:
    Order confirmation or rejection details

#### `execute_trade(self, signal, current_price)`

Execute a paper trade based on AI signal.

Args:
    signal: Trading signal from AI Brain
    current_price: Current market price
    
Returns:
    Trade execution details

#### `execute_simple_trade(self, symbol, action, price, quantity, stop_loss, target)`

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

#### `_execute_buy(self, symbol, quantity, price, stop_loss, target, signal)`

Execute a BUY order

#### `_execute_sell(self, symbol, quantity, price, signal)`

Execute a SELL order

#### `update_positions(self, current_prices)`

Update unrealized P&L for open positions

#### `get_positions(self)`

Get current positions and their status

#### `get_account_info(self)`

Get account information and performance metrics

#### `get_trade_history(self, limit)`

Get recent trade history

#### `_validate_trade(self, symbol, action, quantity, price)`

Validate trade parameters - FIXED VERSION

#### `_log_trade(self, trade)`

Log trade to file

#### `generate_performance_report(self)`

Generate detailed performance report

#### `_calculate_consecutive_wins(self)`

Calculate maximum consecutive winning trades

#### `_calculate_consecutive_losses(self)`

Calculate maximum consecutive losing trades

#### `_calculate_sharpe_ratio(self)`

Calculate Sharpe ratio (simplified)

#### `_calculate_profit_factor(self)`

Calculate profit factor (gross profit / gross loss)

## Functions

### `main()`

Test paper trader

### `__init__(self, initial_capital)`

Initialize paper trader with starting capital

### `place_order(self, symbol, quantity, order_type, price)`

Place a paper trade order.

Args:
    symbol: Stock symbol
    quantity: Number of shares
    order_type: BUY or SELL
    price: Limit price (uses current price if None)
    
Returns:
    Order confirmation or rejection details

### `execute_trade(self, signal, current_price)`

Execute a paper trade based on AI signal.

Args:
    signal: Trading signal from AI Brain
    current_price: Current market price
    
Returns:
    Trade execution details

### `execute_simple_trade(self, symbol, action, price, quantity, stop_loss, target)`

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

### `_execute_buy(self, symbol, quantity, price, stop_loss, target, signal)`

Execute a BUY order

### `_execute_sell(self, symbol, quantity, price, signal)`

Execute a SELL order

### `update_positions(self, current_prices)`

Update unrealized P&L for open positions

### `get_positions(self)`

Get current positions and their status

### `get_account_info(self)`

Get account information and performance metrics

### `get_trade_history(self, limit)`

Get recent trade history

### `_validate_trade(self, symbol, action, quantity, price)`

Validate trade parameters - FIXED VERSION

### `_log_trade(self, trade)`

Log trade to file

### `generate_performance_report(self)`

Generate detailed performance report

### `_calculate_consecutive_wins(self)`

Calculate maximum consecutive winning trades

### `_calculate_consecutive_losses(self)`

Calculate maximum consecutive losing trades

### `_calculate_sharpe_ratio(self)`

Calculate Sharpe ratio (simplified)

### `_calculate_profit_factor(self)`

Calculate profit factor (gross profit / gross loss)

