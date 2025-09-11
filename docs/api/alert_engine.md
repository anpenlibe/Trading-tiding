# alert_engine

Smart alert system for event-driven trading.

## Class: `AlertType`

## Class: `Alert`

Alert data structure.

## Class: `AlertEngine`

Core alert engine.

### Methods

#### `__init__(self)`

#### `add_rule(self, rule)`

Add alert rule.

#### `register_callback(self, alert_type, callback)`

Register callback for alert type.

#### `check_conditions(self, market_data)`

Check all alert conditions.

#### `_trigger_alert(self, alert)`

Execute callbacks for triggered alert.

#### `_in_cooldown(self, rule_name)`

Check if rule is in cooldown.

#### `_create_alert(self, rule, market_data)`

Create alert from triggered rule.

## Class: `AlertRule`

Base class for alert rules.

### Methods

#### `__init__(self, name, alert_type, condition, threshold, priority, cooldown_minutes)`

#### `check(self, market_data)`

Check if condition is met.

#### `get_current_value(self, market_data)`

Get current value being checked.

#### `get_metadata(self, market_data)`

Get additional metadata.

## Functions

### `__init__(self)`

### `add_rule(self, rule)`

Add alert rule.

### `register_callback(self, alert_type, callback)`

Register callback for alert type.

### `check_conditions(self, market_data)`

Check all alert conditions.

### `_trigger_alert(self, alert)`

Execute callbacks for triggered alert.

### `_in_cooldown(self, rule_name)`

Check if rule is in cooldown.

### `_create_alert(self, rule, market_data)`

Create alert from triggered rule.

### `__init__(self, name, alert_type, condition, threshold, priority, cooldown_minutes)`

### `check(self, market_data)`

Check if condition is met.

### `get_current_value(self, market_data)`

Get current value being checked.

### `get_metadata(self, market_data)`

Get additional metadata.

