# config

Module: config.py
Purpose: Configuration settings for the trading bot
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-30 - UPDATED: Now uses centralized stock registry

CHANGES:
- SYMBOLS now imported from stock_registry.py
- Added trading strategy symbol selection
- Improved symbol management with sector awareness

## Functions

### `get_trading_symbols(strategy)`

Get symbols for specific trading strategy.

Args:
    strategy: "conservative", "swing", "diversified", "tech_focus", or None for current

Returns:
    List of trading symbols

### `switch_trading_strategy(new_strategy)`

Switch to a different trading strategy.

Args:
    new_strategy: "conservative", "swing", "diversified", "tech_focus"

### `get_symbol_info(symbol)`

Get detailed information about a trading symbol.

Args:
    symbol: Stock symbol
    
Returns:
    Dict with symbol information or empty dict if not found

### `validate_config()`

### `is_market_hours(timestamp)`

### `calculate_position_size(capital, risk_percent, entry_price, stop_loss)`

