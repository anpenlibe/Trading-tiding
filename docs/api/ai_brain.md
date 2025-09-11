# ai_brain

AI brain with enhanced error handling.

## Class: `ClaudeAI`

Claude AI with robust error handling.

### Methods

#### `__init__(self, api_key)`

Initialize with error handling.

#### `get_required_indicators(self)`

Return list of indicators this model needs.

#### `analyze(self, market_data, indicators)`

Analyze market with comprehensive error handling.

#### `_validate_decision(self, decision)`

Validate AI decision structure.

#### `_safe_default_response(self, reason)`

Return safe default response.

#### `_fallback_analysis(self, market_data, indicators)`

Simple rule-based fallback when AI is unavailable.

#### `_get_claude_response(self, prompt)`

Get response from Claude API with retry logic.

#### `_log_decision(self, symbol, decision, market_data, indicators)`

Log trading decision for analysis.

#### `get_decision_history(self)`

Get recent decision history.

#### `get_performance_stats(self)`

Get AI performance statistics.

#### `reset_history(self)`

Reset decision history.

## Functions

### `__init__(self, api_key)`

Initialize with error handling.

### `get_required_indicators(self)`

Return list of indicators this model needs.

### `analyze(self, market_data, indicators)`

Analyze market with comprehensive error handling.

### `_validate_decision(self, decision)`

Validate AI decision structure.

### `_safe_default_response(self, reason)`

Return safe default response.

### `_fallback_analysis(self, market_data, indicators)`

Simple rule-based fallback when AI is unavailable.

### `_get_claude_response(self, prompt)`

Get response from Claude API with retry logic.

### `_log_decision(self, symbol, decision, market_data, indicators)`

Log trading decision for analysis.

### `get_decision_history(self)`

Get recent decision history.

### `get_performance_stats(self)`

Get AI performance statistics.

### `reset_history(self)`

Reset decision history.

