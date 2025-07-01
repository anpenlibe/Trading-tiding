# 📂 src/ - Core Trading System Modules

This directory contains the **core modules** that power the Claude AI trading system. Each module has a specific responsibility and follows clean architecture principles with proper interfaces and separation of concerns.

---

## 🏗️ **Module Architecture Overview**

```
🧠 AI Layer        → ai_brain.py (Claude integration)
🛡️ Risk Layer      → risk_manager.py (Capital protection)  
💰 Execution Layer → paper_trader.py (Trade simulation)
📊 Data Layer      → data_collector.py, indicator_engine.py, data_sources.py
📋 Management      → stock_registry.py, config.py
🔌 Foundation      → interfaces.py (Abstract contracts)
📝 Utilities       → utils/logger.py (Logging infrastructure)
```

---

## 🧠 **AI & Decision Making**

### **ai_brain.py** - Claude API Integration
**Purpose**: Integrates Claude AI for intelligent trading decisions  
**Key Classes**: `ClaudeAI`, `SimpleRuleBasedModel`

```python
from src.ai_brain import ClaudeAI

# Initialize Claude for trading decisions
ai = ClaudeAI()
decision = ai.analyze(market_data, indicators)

# Returns: {signal, confidence, reasoning, stop_loss, target, position_size}
```

**Features**:
- Comprehensive market analysis with Claude API
- Detailed prompt engineering for trading context
- Decision confidence scoring and reasoning
- Risk manager integration for position sizing
- Decision logging and history tracking

**Dependencies**: `anthropic`, `risk_manager.py`, `interfaces.py`

---

## 🛡️ **Risk Management**

### **risk_manager.py** - Capital Protection System
**Purpose**: Professional position sizing and risk validation  
**Key Classes**: `SimpleRiskManager`, `RiskParameters`

```python
from src.risk_manager import SimpleRiskManager

# Calculate position size and risk parameters
risk_mgr = SimpleRiskManager()
risk_params = risk_mgr.calculate_risk_parameters(
    symbol="RELIANCE",
    signal_type="BUY", 
    entry_price=2850,
    capital=10000
)

# Returns: RiskParameters with position_size, stop_loss, target, etc.
```

**Features**:
- Kelly Criterion-inspired position sizing
- Trade validation against risk rules
- Portfolio risk calculation
- Commission and slippage handling
- Risk-reward ratio enforcement (minimum 1.5:1)

**Dependencies**: `interfaces.py`, `config.py`

---

## 💰 **Trade Execution & Tracking**

### **paper_trader.py** - Trading Simulation System
**Purpose**: Execute and track simulated trades with realistic conditions  
**Key Classes**: `PaperTrader`, `PaperTrade`

```python
from src.paper_trader import PaperTrader

# Initialize paper trader
trader = PaperTrader(initial_capital=10000)

# Execute trade from AI signal
result = trader.execute_trade(signal, current_price)

# Get performance metrics
performance = trader.get_account_info()
```

**Features**:
- Realistic trade simulation with slippage and commissions
- Automatic stop-loss and target execution
- Comprehensive performance tracking (win rate, Sharpe ratio, drawdown)
- Position management and P&L calculation
- Detailed trade logging and history

**Dependencies**: `interfaces.py`, `config.py`

---

## 📊 **Data Pipeline**

### **data_collector.py** - Unified Data Collection
**Purpose**: Orchestrate market data collection, validation, and storage  
**Key Classes**: `DataCollector`, `MemoryCache`, `DataValidator`, `DatabaseManager`

```python
from src.data_collector import DataCollector

# Collect and store market data with indicators
collector = DataCollector()
success = collector.collect_and_store("RELIANCE")

# Get recent data for analysis
data = collector.get_recent_data("RELIANCE", periods=50)
```

**Features**:
- Multi-source data collection with fallback
- Real-time data validation and quality checks
- Technical indicator calculation integration
- SQLite database management with optimization
- Memory caching for performance (5-minute TTL)

**Dependencies**: `data_sources.py`, `indicator_engine.py`, `interfaces.py`, `config.py`

### **indicator_engine.py** - Technical Analysis
**Purpose**: Calculate technical indicators from OHLCV data  
**Key Functions**: `compute_indicators()`

```python
from src.indicator_engine import compute_indicators

# Calculate indicators for latest data point
indicators = compute_indicators(market_data, ['rsi', 'macd', 'sma_20'])

# Returns: {'rsi': 45.2, 'macd': 2.3, 'sma_20': 2850.5}
```

**Features**:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)  
- SMA (Simple Moving Averages) - configurable periods
- Robust error handling with safe fallbacks
- Optimized for performance

**Dependencies**: `pandas`, `numpy`

### **data_sources.py** - Market Data APIs
**Purpose**: Implement market data source interfaces  
**Key Classes**: `ZerodhaAPI`, `MockAPI`

```python
from src.data_sources import ZerodhaAPI, MockAPI

# Production data source
zerodha = ZerodhaAPI()
data = zerodha.fetch_ohlc("RELIANCE")

# Testing/development data source  
mock = MockAPI()
test_data = mock.fetch_ohlc("RELIANCE")
```

**Features**:
- Zerodha KiteConnect integration with token mapping
- Mock data generator for testing and development
- Proper interface implementation for polymorphism
- Error handling and availability checking

**Dependencies**: `kiteconnect`, `interfaces.py`, `config.py`

---

## 📋 **Management & Configuration**

### **stock_registry.py** - Stock Universe Management
**Purpose**: Centralized stock management with sector classification  
**Key Classes**: `StockRegistry`, `Stock`, `Sector`

```python
from src.stock_registry import get_active_symbols, get_symbols_by_sector, Sector

# Get all active trading symbols
symbols = get_active_symbols()

# Get sector-specific stocks
banking_stocks = get_symbols_by_sector(Sector.BANKING)
tech_stocks = get_symbols_by_sector(Sector.TECHNOLOGY)
```

**Features**:
- 24 NSE stocks across 8 sectors (Banking, Technology, Energy, etc.)
- Liquidity ratings and market cap classifications
- Strategy-based portfolio selection (Conservative, Swing, Diversified, Tech Focus)
- Easy stock activation/deactivation
- Sector-based filtering and analysis

**Dependencies**: `dataclasses`, `enum`

### **config.py** - System Configuration
**Purpose**: Centralized configuration management  
**Key Features**: Trading parameters, API settings, market hours

```python
from src.config import SYMBOLS, INITIAL_CAPITAL, is_market_hours

# Trading configuration
capital = INITIAL_CAPITAL  # 10000
risk_per_trade = MAX_RISK_PER_TRADE  # 0.015 (1.5%)

# Market timing
if is_market_hours():
    # Execute trading logic
    pass
```

**Features**:
- Trading parameters (capital, risk limits, position sizing)
- API configuration (Anthropic, Zerodha)
- Market hours and timezone handling
- Strategy settings and risk management parameters
- Environment variable integration with validation

**Dependencies**: `python-dotenv`, `pytz`

---

## 🔌 **Foundation Layer**

### **interfaces.py** - System Contracts
**Purpose**: Define abstract base classes for all system components  
**Key Classes**: `BaseMarketDataAPI`, `BaseDecisionModel`, `BaseRiskManager`, `BaseTradingExecutor`

```python
from src.interfaces import BaseDecisionModel, MarketData, TradingSignal

# All AI models implement this interface
class MyAI(BaseDecisionModel):
    def analyze(self, market_data, indicators) -> Dict[str, Any]:
        # Implementation here
        pass
```

**Features**:
- Standardized data structures (`MarketData`, `TradingSignal`)
- Abstract base classes for polymorphism
- Contract enforcement for all major components
- Consistent APIs across the system

**Dependencies**: `abc`, `dataclasses`, `pandas`

---

## 📝 **Utilities**

### **utils/logger.py** - Logging Infrastructure
**Purpose**: Provide structured logging for all system components  
**Key Classes**: `TradingLogger`, `ColoredFormatter`

```python
from src.utils.logger import get_data_logger, get_trading_logger

# Get specialized loggers
data_logger = get_data_logger()
trading_logger = get_trading_logger()

# Structured logging
data_logger.log_api_call("zerodha", "RELIANCE", True, 0.234)
trading_logger.log_trade_execution("RELIANCE", "BUY", 100, 2850)
```

**Features**:
- Color-coded console output
- File rotation and error tracking
- Structured logging for trading operations
- Performance and API call tracking
- Centralized error logging across all modules

**Dependencies**: `logging`, `colorama`

---

## 🔄 **Module Dependencies**

### **Dependency Graph**
```
📊 claude_trader.py (Main)
    ├── 🧠 ai_brain.py
    │   ├── 🛡️ risk_manager.py
    │   └── 🔌 interfaces.py
    ├── 💰 paper_trader.py
    │   └── 🔌 interfaces.py
    ├── 📊 data_collector.py
    │   ├── 🌐 data_sources.py
    │   ├── 📈 indicator_engine.py
    │   └── 🔌 interfaces.py
    └── ⚙️ config.py
        └── 📋 stock_registry.py
```

### **Import Guidelines**
```python
# Standard pattern for importing core modules
from src.ai_brain import ClaudeAI
from src.risk_manager import SimpleRiskManager  
from src.paper_trader import PaperTrader
from src.data_collector import DataCollector
from src.indicator_engine import compute_indicators
from src.stock_registry import get_active_symbols
from src.config import SYMBOLS, INITIAL_CAPITAL
```

---

## 🧪 **Testing Integration**

### **Module Testing**
Each module can be tested independently:

```python
# Test individual modules
python -c "from src.ai_brain import ClaudeAI; print('AI Brain OK')"
python -c "from src.risk_manager import SimpleRiskManager; print('Risk Manager OK')"
python -c "from src.paper_trader import PaperTrader; print('Paper Trader OK')"
```

### **Integration Testing**
```python
# Test full integration (from tests/)
python tests/test_trading_session.py      # Complete system test (FREE)
python tests/test_ai_brain.py             # AI-specific testing
python tests/test_data_collector.py       # Data pipeline testing
```

---

## 📈 **Performance Considerations**

### **Optimization Features**
- **Caching**: Memory cache in data_collector.py (5-minute TTL)
- **Database**: Optimized SQLite with WAL mode and indexes
- **API Efficiency**: Smart triggers in AI brain to reduce unnecessary calls
- **Memory Management**: Proper resource cleanup and connection handling

### **Scalability Design**
- **Modular Architecture**: Easy to replace individual components
- **Interface-Based**: Polymorphic design allows different implementations
- **Configuration-Driven**: Easy to adjust parameters without code changes
- **Logging Infrastructure**: Comprehensive monitoring and debugging

---

## 🔧 **Development Guidelines**

### **Adding New Modules**
1. **Define Interface**: Create abstract base class in `interfaces.py`
2. **Implement Module**: Follow existing patterns and error handling
3. **Add Configuration**: Update `config.py` with new parameters
4. **Add Logging**: Use appropriate logger from `utils/logger.py`
5. **Write Tests**: Create corresponding test in `tests/` directory

### **Coding Standards**
- **Type Hints**: Use type annotations for all public methods
- **Error Handling**: Comprehensive exception handling with logging
- **Documentation**: Docstrings for all classes and key methods
- **Interface Compliance**: Implement all abstract methods from base classes

### **Testing Requirements**
- **Unit Tests**: Test individual module functionality
- **Integration Tests**: Test module interactions
- **Mock Data**: Use MockAPI for development and testing
- **Performance Tests**: Validate caching and database performance

---

## 📊 **Module Status Matrix**

| Module | Status | Test Coverage | Documentation | Performance |
|--------|--------|---------------|---------------|-------------|
| **ai_brain.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Optimized |
| **risk_manager.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Fast |
| **paper_trader.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Efficient |
| **data_collector.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Cached |
| **indicator_engine.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Fast |
| **data_sources.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Reliable |
| **stock_registry.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Fast |
| **config.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Validated |
| **interfaces.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Lightweight |
| **utils/logger.py** | ✅ Production | ✅ Complete | ✅ Complete | ✅ Efficient |

---

## 🎯 **Quick Module Reference**

### **For AI Development**
```python
from src.ai_brain import ClaudeAI
from src.interfaces import BaseDecisionModel, TradingSignal
```

### **For Risk Management**
```python
from src.risk_manager import SimpleRiskManager, RiskParameters
from src.config import MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT
```

### **For Data Analysis**
```python
from src.data_collector import DataCollector
from src.indicator_engine import compute_indicators
from src.stock_registry import get_active_symbols, Sector
```

### **For Trading Simulation**
```python
from src.paper_trader import PaperTrader, PaperTrade
from src.interfaces import BaseTradingExecutor
```

---

**All modules are production-ready with comprehensive testing, documentation, and error handling. The architecture supports easy extension and modification while maintaining system stability.**
