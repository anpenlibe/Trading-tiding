# database

Database management for market data.

## Class: `DatabaseManager`

Handle all database operations for market data.

### Methods

#### `__init__(self, db_path)`

Initialize database connection.

#### `_init_database(self)`

Initialize database with required tables.

#### `_create_tables(self)`

Create required database tables.

#### `insert_price_data(self, symbol, data)`

Insert or update price data with flexible timestamp handling.

#### `save_market_data(self, data)`

Save market data to database.

#### `save_indicators(self, symbol, timestamp, indicators)`

Save calculated indicators to database.

#### `get_recent_data(self, symbol, periods)`

Get recent price data for a symbol.

#### `get_previous_close(self, symbol)`

Get previous closing price for validation.

#### `log_data_quality_issue(self, symbol, issue_type, description, severity)`

Log data quality issues.

#### `get_stats(self)`

Get database statistics.

#### `close(self)`

Close database connection.

## Functions

### `__init__(self, db_path)`

Initialize database connection.

### `_init_database(self)`

Initialize database with required tables.

### `_create_tables(self)`

Create required database tables.

### `insert_price_data(self, symbol, data)`

Insert or update price data with flexible timestamp handling.

### `save_market_data(self, data)`

Save market data to database.

### `save_indicators(self, symbol, timestamp, indicators)`

Save calculated indicators to database.

### `get_recent_data(self, symbol, periods)`

Get recent price data for a symbol.

### `get_previous_close(self, symbol)`

Get previous closing price for validation.

### `log_data_quality_issue(self, symbol, issue_type, description, severity)`

Log data quality issues.

### `get_stats(self)`

Get database statistics.

### `close(self)`

Close database connection.

