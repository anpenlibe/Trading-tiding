# indicator_engine

Module: indicator_engine.py
Purpose: Unified technical indicator calculations for the trading bot
Author: Trading Bot Developer
Created: 2025-06-13
Modified: 2025-06-30 - Enhanced with complete indicator set, now single source of truth

## Functions

### `compute_indicators(df, indicators)`

Computes a dictionary of indicator values for the latest row in df.
df should have columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']

Args:
    df: DataFrame with OHLCV data
    indicators: List of indicators to compute. If None, computes all available.

Returns:
    Dict of indicator_name -> value for the latest data point

### `calculate_sma(data, period)`

Calculate Simple Moving Average

### `calculate_rsi(data, period)`

Calculate Relative Strength Index

### `calculate_macd(data, fast, slow, signal)`

Calculate MACD indicator with all components

### `calculate_price_change_pct(data)`

Calculate price change percentage from previous period

### `calculate_all_indicators(df)`

Calculate all available indicators for the latest data point.
This is the main function that should be used by data collectors.

Args:
    df: DataFrame with OHLCV data
    
Returns:
    Dict of all calculated indicators

