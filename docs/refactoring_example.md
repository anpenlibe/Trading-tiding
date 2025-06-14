# Refactoring DataCollector with Interfaces

## How to Update Your DataCollector

Replace the API initialization in `data_collector.py`:

```python
from src.interfaces import BaseMarketDataAPI, MarketData
from src.data_sources import DhanAPI, YFinanceAPI, TwelveDataAPI
from typing import List

class DataCollector:
    def __init__(self):
        # ... other initialization ...
        
        # Initialize APIs using the interface
        self.apis: List[BaseMarketDataAPI] = [
            DhanAPI(),      # Primary
            YFinanceAPI(),  # Fallback 1
            TwelveDataAPI() # Fallback 2
        ]
        
        # Filter out unavailable APIs
        self.apis = [api for api in self.apis if api.is_available()]
        
        logger.logger.info(f"Available APIs: {[api.get_name() for api in self.apis]}")
    
    def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        """Fetch data with automatic fallback to backup sources"""
        # Check cache first
        cache_key = f"ohlc_{symbol}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            self.stats['cache_hits'] += 1
            return cached_data
        
        # Try each API in order
        for api in self.apis:
            api_name = api.get_name()
            self.stats['api_calls'][api_name] += 1
            
            try:
                data = api.fetch_ohlc(symbol)
                if data:
                    # Validate and cache as before
                    # ...
                    return data
            except Exception as e:
                logger.logger.error(f"Error with {api_name}: {e}")
                continue
        
        return None
```

## Benefits of This Approach

1. **Type Safety**: The type system ensures all APIs implement required methods
2. **Easy Extension**: Add new APIs by implementing the interface
3. **Testing**: Create mock implementations easily
4. **Flexibility**: Swap implementations at runtime

## Example: Adding a New API

```python
class AlphaVantageAPI(BaseMarketDataAPI):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_KEY')
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        # Implementation here
        pass
    
    def is_available(self) -> bool:
        return bool(self.api_key)

# Just add to the list:
self.apis.append(AlphaVantageAPI())
```

## Future: Decision Model Interface

When you build `ai_brain.py`:

```python
from src.interfaces import BaseDecisionModel

class ClaudeDecisionModel(BaseDecisionModel):
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def analyze(self, market_data: pd.DataFrame, 
                indicators: Dict[str, float]) -> Dict[str, Any]:
        # Format prompt for Claude
        # Send to Claude API
        # Parse response
        return {
            "signal": "BUY",
            "confidence": 0.85,
            "reasoning": "Strong uptrend with RSI support",
            "stop_loss": 2800,
            "target": 2950
        }
    
    def get_required_indicators(self) -> List[str]:
        return ["sma_20", "sma_50", "rsi_14", "macd"]

class SimpleRuleBasedModel(BaseDecisionModel):
    def analyze(self, market_data: pd.DataFrame, 
                indicators: Dict[str, float]) -> Dict[str, Any]:
        # Simple rule: Buy if price > SMA20 and RSI < 70
        if indicators.get('sma_20') and indicators.get('rsi_14'):
            if (market_data['close'].iloc[-1] > indicators['sma_20'] and 
                indicators['rsi_14'] < 70):
                return {"signal": "BUY", "confidence": 0.6, ...}
        return {"signal": "HOLD", "confidence": 0.5, ...}
```