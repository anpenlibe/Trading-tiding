# validator

Market data validation utilities.

## Class: `DataValidator`

Validate market data for quality and consistency.

### Methods

#### `__init__(self)`

Initialize validator with thresholds.

#### `validate(self, data, previous_close)`

Validate market data.

Returns:
    Tuple of (is_valid, error_message)

#### `get_stats(self)`

Get validation statistics.

#### `reset_stats(self)`

Reset validation statistics.

#### `is_data_quality_good(self, threshold)`

Check if overall data quality is above threshold.

## Functions

### `__init__(self)`

Initialize validator with thresholds.

### `validate(self, data, previous_close)`

Validate market data.

Returns:
    Tuple of (is_valid, error_message)

### `get_stats(self)`

Get validation statistics.

### `reset_stats(self)`

Reset validation statistics.

### `is_data_quality_good(self, threshold)`

Check if overall data quality is above threshold.

