# ai_brain

Multi-provider AI decision model with automatic fallback.

**Updated**: 2025-10-03 - Refactored to use ProviderCoordinator

## Class: `AIBrain`

AI decision model with multi-provider fallback support (Groq → Gemini → Claude → rule-based).

### Constructor

#### `__init__(self, api_key=None, temperature=0.6)`

Initialize AI brain with provider coordinator.

**Args:**
- `api_key` (Optional[str]): Deprecated, kept for backward compatibility
- `temperature` (float): Sampling temperature for all providers (default: 0.6)

**Example:**
```python
from src.core.ai_brain import AIBrain

ai = AIBrain()
# Automatically initializes multi-provider fallback chain
```

### Public Methods

#### `get_required_indicators(self) -> list`

Return list of technical indicators required for analysis.

**Returns:**
- List of indicator names: `["sma_20", "sma_50", "sma_200", "rsi_14", "macd", ...]`

#### `analyze(self, market_data: pd.DataFrame, indicators: Dict[str, float]) -> Dict[str, Any]`

Analyze single stock market data and generate trading decision.

**Args:**
- `market_data`: Historical price DataFrame with columns: `[symbol, open, high, low, close, volume]`
- `indicators`: Calculated technical indicators dict

**Returns:**
- Trading decision dict:
  ```python
  {
      'signal': 'BUY' | 'SELL' | 'HOLD',
      'confidence': 0.0-1.0,
      'reasoning': str,
      'entry_price': float,
      'stop_loss': float,
      'target': float,
      'position_size': int,
      'risk_amount': float
  }
  ```

#### `analyze_portfolio_with_intelligent_fallback(self, portfolio_data, portfolio_indicators, context=None) -> Dict[str, Any]`

Analyze entire portfolio at once (batch analysis for multiple stocks).

**Args:**
- `portfolio_data`: Dict of {symbol: DataFrame}
- `portfolio_indicators`: Dict of {symbol: indicators_dict}
- `context`: Optional context dict with `current_positions`, `timestamp`, etc.

**Returns:**
- Portfolio analysis dict:
  ```python
  {
      'market_analysis': str,
      'decisions': {symbol: decision_dict, ...},
      'symbols_analyzed': int,
      'timestamp': datetime
  }
  ```

**Note:** Coordinator handles automatic fallback between providers if rate limits hit.

#### `get_decision_history(self) -> list`

Get recent decision history (last 100 decisions).

**Returns:**
- List of decision records with timestamp, symbol, signal, confidence, reasoning

#### `get_performance_stats(self) -> Dict[str, Any]`

Get AI performance statistics.

**Returns:**
- Stats dict:
  ```python
  {
      'total_decisions': int,
      'buy_signals': int,
      'sell_signals': int,
      'hold_signals': int,
      'avg_confidence': float,
      'high_confidence_decisions': int,
      'last_decision_time': datetime
  }
  ```

#### `reset_history(self)`

Reset decision history.

### Private Methods

#### `_get_ai_response(self, prompt: str, max_tokens: Optional[int] = None) -> str`

Get AI response using coordinator with automatic fallback.

#### `_validate_decision(self, decision: Dict[str, Any]) -> bool`

Validate AI decision structure (checks required fields and value ranges).

#### `_safe_default_response(self, reason: str) -> Dict[str, Any]`

Return safe default HOLD response when analysis fails.

#### `_log_decision(self, symbol, decision, market_data, indicators)`

Log trading decision for analysis and history tracking.

## Legacy Alias

For backward compatibility with external scripts:

```python
ClaudeAI = AIBrain  # Deprecated alias
```

**Migration:** Update imports from `ClaudeAI` to `AIBrain`.

## Architecture

```
AIBrain
  └── ProviderCoordinator
       ├── Groq llama-3.3-70b (Primary)
       ├── Groq llama-3.1-70b (Secondary)
       ├── Gemini 2.5 Pro (Tertiary)
       ├── Claude 3.5 Sonnet (Optional)
       └── Rule-based fallback (Final)
```

See `src/ai/README.md` for detailed architecture documentation.
