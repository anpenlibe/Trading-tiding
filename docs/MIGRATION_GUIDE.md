# Migration Guide: Implementing Abstract Base Classes

## Overview
We've refactored the data collection system to use abstract base classes (interfaces). This provides better code organization, type safety, and makes it easier to add new data sources.

## Files Created/Modified

### New Files:
1. **`src/interfaces.py`** - Abstract base classes
2. **`src/data_sources.py`** - Concrete API implementations
3. **`docs/refactoring_example.md`** - Usage examples

### Modified Files:
1. **`src/data_collector.py`** - Updated to use interfaces

## Key Changes in data_collector.py

### 1. Imports
```python
# Old
# (APIs were defined in the same file)

# New
from src.interfaces import BaseMarketDataAPI, MarketData
from src.data_sources import DhanAPI, YFinanceAPI, TwelveDataAPI
```

### 2. API Initialization
```python
# Old
self.apis = [
    DhanAPI(),
    YFinanceAPI(),
    TwelveDataAPI()
]

# New
self.apis: List[BaseMarketDataAPI] = [
    DhanAPI(),
    YFinanceAPI(),
    TwelveDataAPI()
]

# Filter out unavailable APIs
available_apis = []
for api in self.apis:
    if api.is_available():
        available_apis.append(api)
        logger.logger.info(f"API {api.get_name()} is available")
    else:
        logger.logger.warning(f"API {api.get_name()} is not available")

self.apis = available_apis
```

### 3. API Usage
```python
# Old
api_name = api.__class__.__name__

# New
api_name = api.get_name()
```

## Benefits

1. **Type Safety**: The type system ensures all APIs implement required methods
2. **Easy Extension**: Add new APIs by implementing the interface
3. **Better Testing**: Create mock implementations easily
4. **Code Organization**: APIs are in separate files, easier to maintain

## How to Add a New API

1. Create a new class in `src/data_sources.py`:
```python
class NewAPI(BaseMarketDataAPI):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('NEW_API_KEY')
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        # Your implementation
        pass
    
    def is_available(self) -> bool:
        return bool(self.api_key)
```

2. Add it to DataCollector in `data_collector.py`:
```python
self.apis: List[BaseMarketDataAPI] = [
    DhanAPI(),
    YFinanceAPI(),
    TwelveDataAPI(),
    NewAPI()  # Just add here!
]
```

## Testing the Changes

Run the test script to ensure everything works:
```bash
python test_data_collector.py
```

## Next Steps

When you build `ai_brain.py`, use the `BaseDecisionModel` interface:
```python
from src.interfaces import BaseDecisionModel

class ClaudeAI(BaseDecisionModel):
    def analyze(self, market_data, indicators):
        # Implementation
        pass
    
    def get_required_indicators(self):
        return ["sma_20", "rsi_14", "macd"]
```

This same pattern can be applied to:
- Risk Management (`BaseRiskManager`)
- Trade Execution (`BaseTradingExecutor`)
- Any other component that might have multiple implementations

## Troubleshooting

If you get import errors:
1. Make sure you're in the virtual environment
2. Check that all new files are created
3. Ensure `src/__init__.py` exists
4. Try: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`