# logger

Module: logger.py
Purpose: Centralized logging configuration for trading bot
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-12

## Class: `ColoredFormatter`

Custom formatter with colors for console output

### Methods

#### `format(self, record)`

## Class: `TradingLogger`

Specialized logger for trading operations with structured logging

### Methods

#### `__init__(self, name, log_file)`

#### `log_api_call(self, api_name, symbol, success, response_time, error)`

Log API call with structured data

#### `log_data_quality(self, symbol, issue, severity)`

Log data quality issues

#### `log_indicator_calculation(self, symbol, indicator, value)`

Log indicator calculations

#### `log_cache_operation(self, operation, symbol, hit)`

Log cache operations

#### `log_database_operation(self, operation, table, records, duration)`

Log database operations

#### `log_daily_summary(self, stats)`

Log daily summary statistics

## Functions

### `setup_logger(name, log_file, level, console_output, max_bytes, backup_count)`

Set up a logger with file and console handlers.

Args:
    name: Logger name (usually __name__)
    log_file: Log file name (without path)
    level: Logging level
    console_output: Whether to output to console
    max_bytes: Maximum size of log file before rotation
    backup_count: Number of backup files to keep
    
Returns:
    Configured logger instance

### `get_data_logger()`

Get logger for data collection module

### `get_trading_logger()`

Get logger for trading operations

### `get_ai_logger()`

Get logger for AI brain module

### `get_monitor_logger()`

Get logger for monitoring module

### `format(self, record)`

### `__init__(self, name, log_file)`

### `log_api_call(self, api_name, symbol, success, response_time, error)`

Log API call with structured data

### `log_data_quality(self, symbol, issue, severity)`

Log data quality issues

### `log_indicator_calculation(self, symbol, indicator, value)`

Log indicator calculations

### `log_cache_operation(self, operation, symbol, hit)`

Log cache operations

### `log_database_operation(self, operation, table, records, duration)`

Log database operations

### `log_daily_summary(self, stats)`

Log daily summary statistics

