# data_collector

Enhanced data collector with robust error handling.

## Class: `DataCollector`

Data collector with enhanced error handling.

### Methods

#### `__init__(self)`

Initialize with error handling.

#### `_init_database(self)`

Initialize database with retry logic.

#### `_init_apis(self)`

Initialize APIs with circuit breakers.

#### `collect_and_store(self, symbol)`

Collect data with comprehensive error handling.

#### `_store_data(self, symbol, market_data)`

Store data with retry logic.

#### `collect_all_symbols(self)`

Collect data for all configured symbols.

#### `get_recent_data(self, symbol, periods)`

Get recent data with error handling.

#### `fetch_with_fallback(self, symbol)`

Fetch data with automatic fallback to backup sources.

#### `process_and_save(self, data)`

Process and save market data with indicators.

#### `get_stats(self)`

Get collection statistics.

#### `close(self)`

Clean shutdown with error handling.

#### `save_market_data(self, data)`

Legacy method for compatibility.

#### `save_indicators(self, symbol, timestamp, indicators)`

Legacy method for compatibility.

## Functions

### `__init__(self)`

Initialize with error handling.

### `_init_database(self)`

Initialize database with retry logic.

### `_init_apis(self)`

Initialize APIs with circuit breakers.

### `collect_and_store(self, symbol)`

Collect data with comprehensive error handling.

### `_store_data(self, symbol, market_data)`

Store data with retry logic.

### `collect_all_symbols(self)`

Collect data for all configured symbols.

### `get_recent_data(self, symbol, periods)`

Get recent data with error handling.

### `fetch_with_fallback(self, symbol)`

Fetch data with automatic fallback to backup sources.

### `process_and_save(self, data)`

Process and save market data with indicators.

### `get_stats(self)`

Get collection statistics.

### `close(self)`

Clean shutdown with error handling.

### `save_market_data(self, data)`

Legacy method for compatibility.

### `save_indicators(self, symbol, timestamp, indicators)`

Legacy method for compatibility.

