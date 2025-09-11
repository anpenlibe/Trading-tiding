# 🏗️ System Architecture Lookup Table

**Version**: 3.0 (Post Phase 3 Reorganization)  
**Purpose**: Central architecture reference for system-wide changes  
**Maintenance**: Update this document first when making architectural changes  

---

## 🎯 Architecture Overview

```
📱 APPLICATIONS LAYER    → apps/
🧠 BUSINESS LOGIC LAYER  → src/core/
📊 DATA LAYER           → src/data/
⚡ ALERT SYSTEM         → src/alerts/
🤖 AI COMPONENTS        → src/ai/
📈 MONITORING           → src/monitoring/
🔧 UTILITIES            → src/utils/
🧪 TESTING              → tests/
📚 DOCUMENTATION        → docs/
```

---

## 🔍 Change Impact Matrix

**Use this table to identify all affected components when making changes:**

| **Component** | **Direct Dependencies** | **Dependent Components** | **Config Impact** | **Test Impact** |
|---------------|------------------------|--------------------------|-------------------|-----------------|
| **src/core/ai_brain.py** | interfaces.py, risk_manager.py, config.py | apps/trader.py, apps/backtest.py | ANTHROPIC_API_KEY, CLAUDE_MODEL | tests/unit/test_ai_brain.py, tests/integration/ |
| **src/core/risk_manager.py** | interfaces.py, config.py | ai_brain.py, paper_trader.py, apps/trader.py | MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT | tests/unit/test_risk_manager.py |
| **src/core/paper_trader.py** | interfaces.py, config.py | apps/trader.py, apps/backtest.py | INITIAL_CAPITAL, commission settings | tests/unit/test_paper_trader.py |
| **src/data/config.py** | stock_registry.py | **ALL MODULES** | ALL environment variables | tests/unit/test_config.py |
| **src/data_collector.py** | data_sources.py, indicator_engine.py, config.py, trading_modes.py | apps/trader.py, apps/backtest.py, apps/data_collector.py | DB_PATH, SYMBOLS, TRADING_MODE | tests/unit/test_data_collector.py |
| **src/data/data_sources.py** | interfaces.py, config.py | data_collector.py | ZERODHA_API_KEY, ZERODHA_ACCESS_TOKEN | tests/unit/test_data_sources.py |
| **src/core/indicator_engine.py** | None (standalone) | data_collector.py, apps/backtest.py | RSI_PERIOD, MACD_FAST/SLOW/SIGNAL | tests/unit/test_indicator_engine.py |
| **src/alerts/alert_engine.py** | interfaces.py, config.py | apps/trader.py | ENABLE_ALERTS, alert thresholds | tests/test_alerts.py |
| **src/interfaces.py** | None (base definitions) | **ALL CORE MODULES** | None | All test files |
| **src/core/trading_modes.py** | interfaces.py, exceptions.py | data_collector.py, trader.py | TRADING_MODE, DRY_RUN | tests/unit/test_trading_modes.py |

---

## 🔄 Dependency Chains

### **Critical Path 1: Trading Decision Flow**
```
apps/trader.py
  ├── src/data_collector.py
  │   ├── src/data/data_sources.py (Zerodha API)
  │   └── src/core/indicator_engine.py
  ├── src/core/ai_brain.py (Claude API)
  │   └── src/core/risk_manager.py
  └── src/core/paper_trader.py
```

### **Critical Path 2: Alert System Flow**
```
apps/trader.py (alert mode)
  ├── src/alerts/alert_engine.py
  │   └── src/alerts/rules.py
  ├── src/data_collector.py (lightweight polling)
  └── [same trading decision flow when alert triggered]
```

### **Critical Path 3: Data Collection Flow**
```
apps/data_collector.py
  ├── src/data_collector.py
  │   ├── src/data/data_sources.py
  │   ├── src/core/indicator_engine.py
  │   └── src/data/database.py
  └── src/data/config.py
```

---

## 📋 Module Responsibility Matrix

| **Module** | **Primary Responsibility** | **Secondary Functions** | **External APIs** | **Database Tables** |
|------------|---------------------------|------------------------|-------------------|-------------------|
| **apps/trader.py** | Trading orchestration | Performance tracking, error recovery | Claude API, Zerodha API | Via data_collector |
| **apps/backtest.py** | Historical simulation | Performance analysis | Claude API (optional) | price_data (read-only) |
| **apps/data_collector.py** | Data collection utility | Database management | Zerodha API | price_data, indicators |
| **apps/monitor.py** | System monitoring | Performance dashboard | None | price_data, data_quality_log |
| **src/core/ai_brain.py** | AI decision making | Prompt engineering, confidence scoring | Claude API | None |
| **src/core/risk_manager.py** | Risk calculations | Trade validation, position sizing | None | None |
| **src/core/paper_trader.py** | Trade execution | Performance tracking, P&L calculation | None | None (JSON files) |
| **src/data_collector.py** | Data orchestration | Caching, validation, database ops | Via data_sources | price_data, indicators, data_quality_log |
| **src/data/data_sources.py** | API implementations | Token mapping, error handling | Zerodha API, YFinance | None |
| **src/core/indicator_engine.py** | Technical calculations | RSI, MACD, SMA calculations | None | None |
| **src/alerts/alert_engine.py** | Alert coordination | Rule evaluation, callback management | None | None |
| **src/alerts/rules.py** | Alert conditions | Price, RSI, volume, MACD alerts | None | None |

---

## 🚨 Safety System Architecture

**CRITICAL COMPONENT**: Financial safety system to prevent trading losses from data source failures.

### **Safety Components**
```
src/core/trading_modes.py
├── TradingMode (Enum)         → PAPER, LIVE, BACKTEST
├── TradingSafetyConfig       → Mode-specific safety settings  
├── TradingSafetyValidator    → Data source validation
└── User confirmation system  → Live trading warnings

src/data_collector.py
├── Safety integration        → Validates all market data
├── Mock API prevention       → Blocks fake data in live mode
└── Live API validation       → Requires working data sources
```

### **Safety Flow**
1. **Initialization**: DataCollector checks trading mode and available APIs
2. **Data Validation**: Every market data point validated against trading mode
3. **API Filtering**: Mock APIs blocked in live trading mode
4. **User Confirmation**: Live trading requires explicit "I UNDERSTAND THE RISKS" confirmation
5. **Runtime Protection**: TradingSystemError exceptions halt unsafe operations

### **Safety Dependencies**
| **Component** | **Safety Impact** | **Failure Mode** | **Protection** |
|---------------|-------------------|-------------------|----------------|
| **DataCollector** | Core data safety | Mock data in live mode | API filtering, source validation |
| **TradingSafetyValidator** | Data source checking | Fake data acceptance | Source validation, mode enforcement |
| **Trading Mode Config** | System-wide safety | Wrong mode selection | Explicit mode setting, confirmation |
| **API Authentication** | Live data access | No live data available | Initialization failure, clear error messages |

---

## ⚙️ Configuration Impact Map

**When changing configuration, update these files:**

### **Environment Variables (.env)**
| **Variable** | **Modules Affected** | **Impact** |
|--------------|---------------------|------------|
| `ANTHROPIC_API_KEY` | ai_brain.py, apps/trader.py, apps/backtest.py | AI decisions stop working |
| `ZERODHA_API_KEY` | data_sources.py, data_collector.py, apps/data_collector.py | Live data stops |
| `SYMBOLS` | config.py, **ALL trading apps** | Changes entire trading universe |
| `DB_PATH` | data_collector.py, apps/backtest.py, apps/monitor.py | Database connection fails |
| `INITIAL_CAPITAL` | paper_trader.py, apps/trader.py | Changes trading capital |
| `MAX_RISK_PER_TRADE` | risk_manager.py, **ALL trading** | Changes position sizes |

### **Code Configuration Changes**
| **Config Change** | **Files to Update** | **Tests to Update** |
|-------------------|-------------------|-------------------|
| Add new indicator | indicator_engine.py, config.py | test_indicator_engine.py |
| Add new symbol | stock_registry.py, config.py | test_config.py, integration tests |
| Change risk model | risk_manager.py, config.py | test_risk_manager.py |
| Add new alert type | alerts/rules.py, alerts/alert_engine.py | test_alerts.py |

---

## 🧪 Testing Impact Matrix

### **Test Categories**
| **Test Type** | **Location** | **Covers** | **Update When** |
|---------------|-------------|------------|-----------------|
| **Unit Tests** | tests/unit/ | Individual modules | Any module changes |
| **Integration Tests** | tests/integration/ | Module interactions | Workflow changes |
| **Alert Tests** | tests/test_alerts.py | Alert system | Alert system changes |
| **System Tests** | apps/trader.py main() | End-to-end flow | Major architectural changes |

### **Test Dependencies**
```
tests/conftest.py (shared fixtures)
  ├── tests/unit/*.py (individual module tests)
  ├── tests/integration/*.py (workflow tests)
  └── tests/test_alerts.py (alert system tests)
```

---

## 📊 Data Flow Architecture

### **Real-Time Trading Flow**
```
1. Market Data Input
   └── ZerodhaAPI → data_collector.py → SQLite DB

2. Alert Evaluation
   └── alert_engine.py → checks conditions → triggers callbacks

3. Decision Making (when triggered)
   └── ai_brain.py → Claude API → TradingSignal

4. Risk Assessment
   └── risk_manager.py → validates signal → RiskParameters

5. Trade Execution
   └── paper_trader.py → simulates trade → updates portfolio
```

### **Historical Simulation Flow**
```
1. Historical Data Query
   └── SQLite DB → backtest.py → chronological replay

2. Simulated Real-Time
   └── SimulationDataCollector → provides time-shifted data

3. Decision Making
   └── [same as real-time but with historical context]

4. Performance Analysis
   └── paper_trader.py → generates metrics → saves report
```

---

## 🔧 Extension Points

**Use these interfaces to add new functionality:**

### **Adding New Data Sources**
1. Implement `BaseMarketDataAPI` in `src/interfaces.py`
2. Add new class to `src/data/data_sources.py`
3. Update `src/data_collector.py` to include new source
4. Add configuration in `src/data/config.py`
5. Create tests in `tests/unit/test_data_sources.py`

### **Adding New AI Models**
1. Implement `BaseDecisionModel` in `src/interfaces.py`
2. Add new class to `src/core/ai_brain.py` or create new module
3. Update `apps/trader.py` to use new model
4. Add configuration in `src/data/config.py`
5. Create tests in `tests/unit/test_ai_brain.py`

### **Adding New Alert Types**
1. Create new rule class in `src/alerts/rules.py`
2. Register rule in `src/alerts/alert_engine.py`
3. Add callback handling in `apps/trader.py`
4. Add configuration in `src/data/config.py`
5. Update `tests/test_alerts.py`

### **Adding New Risk Models**
1. Implement `BaseRiskManager` in `src/interfaces.py`
2. Add new class to `src/core/risk_manager.py`
3. Update `src/core/ai_brain.py` to use new model
4. Add configuration in `src/data/config.py`
5. Create tests in `tests/unit/test_risk_manager.py`

---

## 🚨 Critical System Points

**These components are system-critical - changes require careful coordination:**

### **Single Points of Failure**
1. **src/data/config.py** - All modules depend on this
2. **src/interfaces.py** - All core modules implement these
3. **Database schema** - Changes break historical data compatibility
4. **Claude API integration** - Core to AI decision making

### **High-Impact Changes**
1. **Interface modifications** - Affects all implementations
2. **Database schema changes** - Requires migration strategy
3. **Configuration structure changes** - Breaks existing deployments
4. **Alert system changes** - Affects trading efficiency

---

## 📝 Change Management Protocol

### **Before Making Changes:**
1. **Identify Impact** - Use this document to find all affected components
2. **Update This Document** - Modify architecture tables first
3. **Plan Testing** - Identify all tests that need updates
4. **Check Dependencies** - Verify no breaking changes in dependency chain

### **During Implementation:**
1. **Update Interfaces First** - If changing contracts
2. **Update Configuration** - Before changing implementation
3. **Update Tests** - As you modify components
4. **Update Documentation** - Keep README files current

### **After Implementation:**
1. **Run Full Test Suite** - Ensure no regressions
2. **Update Performance Benchmarks** - If performance changed
3. **Update API Documentation** - If external interfaces changed
4. **Update This Document** - Reflect new reality

---

## 📈 Future Improvements Integration Points

### **🧠 AI Context Memory**
**Architecture Impact:**
- **New Module**: `src/ai/memory.py` (ChromaDB integration)
- **Modified**: `src/core/ai_brain.py` (memory integration)
- **Modified**: `src/data/database.py` (decision history storage)
- **Config Impact**: Memory settings, ChromaDB path
- **Test Impact**: New memory tests, modified AI tests

### **🔄 Test Suite Renewal**
**Architecture Impact:**
- **All Test Files**: Complete review and update
- **New**: Performance benchmarks
- **Modified**: Integration test scenarios
- **No Config Impact**
- **High Test Impact**: All existing tests

### **📊 Multi-Timestamp Data**
**Architecture Impact:**
- **Modified**: `src/data_collector.py` (rolling window fetching)
- **Modified**: `src/core/ai_brain.py` (temporal context handling)
- **Modified**: `apps/backtest.py` (enhanced historical context)
- **Config Impact**: Window sizes, context length
- **Test Impact**: Data collector tests, AI brain tests

### **🔌 Fallback API**
**Architecture Impact:**
- **Modified**: `src/data/data_sources.py` (new API implementations)
- **Modified**: `src/data_collector.py` (fallback logic)
- **Config Impact**: New API keys and settings
- **Test Impact**: Data source tests, collector tests

### **📦 Stock Abstraction**
**Architecture Impact:**
- **Enhanced**: `src/data/stock_registry.py` (complete abstraction)
- **Modified**: All modules using hardcoded symbols
- **Config Impact**: Stock configuration format
- **Test Impact**: All tests using symbols

---

## 🎯 Quick Reference Commands

### **Find All Dependencies of a Module**
```bash
grep -r "from.*module_name\|import.*module_name" src/ apps/ tests/
```

### **Find All References to a Configuration**
```bash
grep -r "CONFIG_NAME" src/ apps/ tests/ .env.template
```

### **Check Interface Implementations**
```bash
grep -r "class.*BaseInterface" src/
```

### **Find Test Coverage for Module**
```bash
find tests/ -name "*module_name*" -o -name "*test*module*"
```

---

**📋 This document should be updated FIRST when making any architectural changes to maintain system integrity and ease maintenance.**