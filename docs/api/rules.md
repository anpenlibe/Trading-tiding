# rules

Predefined alert rules.

## Class: `PriceCrossRule`

Alert when price crosses threshold.

### Methods

#### `__init__(self, symbol, threshold, direction)`

#### `check(self, market_data)`

#### `get_current_value(self, market_data)`

## Class: `RSIExtremeRule`

Alert on RSI extremes.

### Methods

#### `__init__(self, symbol, overbought, oversold)`

#### `check(self, market_data)`

#### `get_current_value(self, market_data)`

#### `get_metadata(self, market_data)`

## Class: `VolumeSpikRule`

Alert on volume spikes.

### Methods

#### `__init__(self, symbol, spike_multiplier)`

#### `check(self, market_data)`

#### `get_current_value(self, market_data)`

#### `get_metadata(self, market_data)`

## Class: `MACDCrossRule`

Alert on MACD signal line crossovers.

### Methods

#### `__init__(self, symbol, direction)`

#### `check(self, market_data)`

#### `get_current_value(self, market_data)`

#### `get_metadata(self, market_data)`

## Functions

### `__init__(self, symbol, threshold, direction)`

### `check(self, market_data)`

### `get_current_value(self, market_data)`

### `__init__(self, symbol, overbought, oversold)`

### `check(self, market_data)`

### `get_current_value(self, market_data)`

### `get_metadata(self, market_data)`

### `__init__(self, symbol, spike_multiplier)`

### `check(self, market_data)`

### `get_current_value(self, market_data)`

### `get_metadata(self, market_data)`

### `__init__(self, symbol, direction)`

### `check(self, market_data)`

### `get_current_value(self, market_data)`

### `get_metadata(self, market_data)`

