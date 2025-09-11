# error_tracker

Error tracking and monitoring.

## Class: `ErrorTracker`

Track and analyze system errors.

### Methods

#### `__init__(self, window_minutes)`

Initialize error tracker.

#### `record_error(self, module, error_type, details)`

Record an error occurrence.

#### `_get_recent_errors(self, module)`

Get errors within the time window.

#### `get_error_summary(self)`

Get comprehensive error summary.

#### `_get_top_errors(self, n)`

Get top N most frequent errors.

#### `_get_all_recent_errors(self, n)`

Get N most recent errors across all modules.

#### `_calculate_error_rate(self)`

Calculate errors per minute.

#### `save_report(self, filepath)`

Save error report to file.

## Functions

### `__init__(self, window_minutes)`

Initialize error tracker.

### `record_error(self, module, error_type, details)`

Record an error occurrence.

### `_get_recent_errors(self, module)`

Get errors within the time window.

### `get_error_summary(self)`

Get comprehensive error summary.

### `_get_top_errors(self, n)`

Get top N most frequent errors.

### `_get_all_recent_errors(self, n)`

Get N most recent errors across all modules.

### `_calculate_error_rate(self)`

Calculate errors per minute.

### `save_report(self, filepath)`

Save error report to file.

