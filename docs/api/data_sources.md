# data_sources

Module: data_sources.py
Purpose: Concrete implementations of market data APIs using interfaces
Author: Trading Bot Developer
Created: 2025-06-13
Modified: 2025-06-30 - Fixed interface compliance

## Class: `ZerodhaAPI`

Zerodha OHLC + Quote Data using Kite Connect

### Methods

#### `__init__(self)`

#### `_load_token_map(self)`

Load instrument token mappings from instruments.csv

#### `fetch_ohlc(self, symbol)`

Fetch current OHLC + volume for the given symbol using Zerodha

#### `is_available(self)`

#### `get_name(self)`

## Class: `MockAPI`

Mock API for testing during market closed hours

### Methods

#### `__init__(self)`

#### `fetch_ohlc(self, symbol)`

Generate mock data with realistic variations

#### `is_available(self)`

Mock is always available

#### `get_name(self)`

## Functions

### `__init__(self)`

### `_load_token_map(self)`

Load instrument token mappings from instruments.csv

### `fetch_ohlc(self, symbol)`

Fetch current OHLC + volume for the given symbol using Zerodha

### `is_available(self)`

### `get_name(self)`

### `__init__(self)`

### `fetch_ohlc(self, symbol)`

Generate mock data with realistic variations

### `is_available(self)`

Mock is always available

### `get_name(self)`

