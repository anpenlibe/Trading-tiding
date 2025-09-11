# stock_registry

Module: stock_registry.py
Purpose: Centralized stock management with sector organization and metadata
Author: Trading Bot Developer
Created: 2025-06-30
Modified: 2025-07-01 - FIXED: Sector filtering and import issues

This module provides centralized stock symbol management with:
- Sector-based organization
- Market cap and liquidity information  
- Trading priority and risk classification
- Easy symbol selection for different strategies

FIXES APPLIED:
- Fixed sector filtering (was returning empty for tech)
- Fixed import path issues
- Improved symbol selection logic

## Class: `Sector`

Stock sectors for Indian market

## Class: `MarketCap`

Market capitalization categories

## Class: `LiquidityRating`

Stock liquidity ratings

## Class: `StockInfo`

Complete stock information

## Class: `StockRegistry`

Centralized stock registry with intelligent selection capabilities.

Features:
- Sector-based organization
- Risk-based filtering
- Liquidity-based selection
- Priority lists for different strategies

### Methods

#### `__init__(self)`

Initialize the stock registry with Indian market stocks

#### `_initialize_stocks(self)`

Initialize with curated list of Indian stocks

#### `_add_stock(self, symbol, company_name, sector, market_cap, liquidity, is_index_stock, is_active, avg_daily_volume, typical_spread_bps, notes)`

Add a stock to the registry

#### `get_all_symbols(self, active_only)`

Get all stock symbols

#### `get_symbols_by_sector(self, sector, active_only)`

Get symbols filtered by sector

#### `get_symbols_by_market_cap(self, market_cap, active_only)`

Get symbols filtered by market cap

#### `get_symbols_by_liquidity(self, liquidity, active_only)`

Get symbols filtered by liquidity rating

#### `get_index_stocks(self, active_only)`

Get symbols that are part of major indices

#### `get_conservative_portfolio(self, max_symbols)`

Get conservative portfolio symbols.

Criteria: Large cap, high liquidity, index stocks, defensive sectors

#### `get_aggressive_portfolio(self, max_symbols)`

Get aggressive portfolio symbols.

Criteria: Include cyclical sectors, mixed market caps

#### `get_swing_trading_symbols(self, max_symbols)`

Get symbols optimized for swing trading.

Criteria: High liquidity, good volatility, tight spreads

#### `get_diversified_portfolio(self, max_symbols)`

Get a diversified portfolio across sectors.

Ensures representation from different sectors and market caps.

#### `get_stock_info(self, symbol)`

Get detailed information for a specific stock

#### `get_sector_summary(self)`

Get summary statistics by sector

#### `save_to_file(self, filepath)`

Save the registry to a JSON file

#### `load_from_file(self, filepath)`

Load the registry from a JSON file

## Functions

### `get_stock_registry()`

Get the global stock registry instance

### `get_conservative_symbols(max_symbols)`

Get conservative trading symbols

### `get_swing_trading_symbols(max_symbols)`

Get symbols optimized for swing trading

### `get_diversified_symbols(max_symbols)`

Get diversified portfolio symbols

### `get_symbols_by_sector(sector_name)`

Get symbols by sector name - FIXED VERSION

### `__init__(self)`

Initialize the stock registry with Indian market stocks

### `_initialize_stocks(self)`

Initialize with curated list of Indian stocks

### `_add_stock(self, symbol, company_name, sector, market_cap, liquidity, is_index_stock, is_active, avg_daily_volume, typical_spread_bps, notes)`

Add a stock to the registry

### `get_all_symbols(self, active_only)`

Get all stock symbols

### `get_symbols_by_sector(self, sector, active_only)`

Get symbols filtered by sector

### `get_symbols_by_market_cap(self, market_cap, active_only)`

Get symbols filtered by market cap

### `get_symbols_by_liquidity(self, liquidity, active_only)`

Get symbols filtered by liquidity rating

### `get_index_stocks(self, active_only)`

Get symbols that are part of major indices

### `get_conservative_portfolio(self, max_symbols)`

Get conservative portfolio symbols.

Criteria: Large cap, high liquidity, index stocks, defensive sectors

### `get_aggressive_portfolio(self, max_symbols)`

Get aggressive portfolio symbols.

Criteria: Include cyclical sectors, mixed market caps

### `get_swing_trading_symbols(self, max_symbols)`

Get symbols optimized for swing trading.

Criteria: High liquidity, good volatility, tight spreads

### `get_diversified_portfolio(self, max_symbols)`

Get a diversified portfolio across sectors.

Ensures representation from different sectors and market caps.

### `get_stock_info(self, symbol)`

Get detailed information for a specific stock

### `get_sector_summary(self)`

Get summary statistics by sector

### `save_to_file(self, filepath)`

Save the registry to a JSON file

### `load_from_file(self, filepath)`

Load the registry from a JSON file

