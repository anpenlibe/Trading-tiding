# TRADING SYSTEM FLOW ANALYSIS
*Last Updated: 2025-09-12*

## PART 1: CURRENT ENTRY POINTS

The system has several applications for different use cases:

### 1. apps/trader.py ✅ MAIN ENTRY POINT
**Purpose**: Main AI-driven trading system
**Entry**: `python apps/trader.py`
**Mode**: Runs a single AI-driven paper-trading cycle, then prints a report (no CLI flags)
**Features**: Alert-based trading, risk management, performance tracking

### 2. apps/data_collector.py ✅ DATA MANAGEMENT  
**Purpose**: Data collection and management
**Entry**: `python apps/data_collector.py`
**Mode**: Interactive data collection and validation
**Features**: Multi-source data, caching, validation

### 3. apps/backtest.py ✅ HISTORICAL TESTING
**Purpose**: Backtesting on historical data
**Entry**: `python apps/backtest.py [--auto] [--days N] [--symbols SYMBOL1,SYMBOL2]`
**Mode**: Historical simulation and performance analysis
**Features**: Non-interactive mode, custom timeframes, multi-symbol support

### 4. apps/monitor.py ✅ MONITORING DASHBOARD
**Purpose**: System monitoring and alerts
**Entry**: `python apps/monitor.py [--auto] [--continuous]`
**Mode**: Real-time system monitoring and health checks
**Features**: Live data monitoring, alert system, export functionality

### 5. apps/health_check.py ✅ SYSTEM DIAGNOSTICS
**Purpose**: Comprehensive system health validation
**Entry**: `python apps/health_check.py [--quick] [--verbose]`
**Mode**: System health verification and diagnostics
**Features**: Database checks, API validation, functionality testing

## PART 2: CORE SYSTEM FLOW

### ✅ Current Trading Flow (apps/trader.py)
```
┌─────────────────┐
│   SYSTEM START  │
│   AI Trader     │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Initialize     │────▶│ DataCollector│────▶│  Database &     │
│  Components     │     │ AI Brain     │     │  Configuration  │
│                 │     │ PaperTrader  │     │                 │
└─────────┬───────┘     │ RiskManager  │     └─────────────────┘
          │             │ AlertEngine  │     
          ▼             └──────────────┘     
┌─────────────────┐
│ TRADING CYCLE   │
│ (Configurable)  │
└─────────┬───────┘
          │
          ▼
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃                    PER-SYMBOL PROCESSING                          ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
          │
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ 1. Fetch Market │────▶│ 2. Calculate │────▶│ 3. AI Decision  │
│ Data (Recent)   │     │ Indicators   │     │ (Claude 3.5)    │
└─────────────────┘     └──────────────┘     └─────────┬───────┘
                                                       │
                                                       ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ 6. Log Results  │◀────│ 5. Execute   │◀────│ 4. Risk         │
│ & Portfolio     │     │ Paper Trade  │     │ Assessment      │
└─────────────────┘     └──────────────┘     └─────────────────┘
          │
          ▼
┌─────────────────┐
│  CYCLE SUMMARY  │
│  Performance    │
│  Metrics        │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│  NEXT CYCLE     │
│ (or END)        │
└─────────────────┘
```

### ✅ Current Data Pipeline Flow
```
┌─────────────────┐
│   DATA SOURCES  │
│                 │
│ • Database      │
│ • ZerodhaAPI    │
│ • MockAPI       │
│ • CSV Files     │ 
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ DataCollector   │────▶│ Cache System │────▶│ DataValidator   │
│                 │     │              │     │                 │
│ • Multi-source  │     │ • Memory     │     │ • OHLCV checks  │
│ • Fallback      │     │ • Disk       │     │ • Range limits  │
│ • Rate Limiting │     │ • TTL        │     │ • Consistency   │
└─────────┬───────┘     └──────────────┘     └─────────┬───────┘
          │                                            │
          ▼                                            ▼
┌─────────────────┐                          ┌─────────────────┐
│   Database      │                          │   MarketData    │
│   Storage       │                          │   Objects       │
│                 │                          │                 │
│ • SQLite        │◀─────────────────────────│ • Validated     │
│ • Optimized     │                          │ • Structured    │
│ • Indexed       │                          │ • Ready for AI  │
└─────────────────┘                          └─────────────────┘
```

### ✅ NEW: Alert System Flow  
```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Market Data     │────▶│ AlertEngine  │────▶│ Condition       │
│ Stream          │     │              │     │ Evaluation      │
│                 │     │ • RSI Rules  │     │                 │
│ • Price         │     │ • MACD Rules │     │ • Threshold     │
│ • Volume        │     │ • Volume     │     │ • Crossover     │
│ • Indicators    │     │ • Price      │     │ • Extreme       │
└─────────────────┘     └──────────────┘     └─────────┬───────┘
                                                       │
                                                       ▼
                                             ┌─────────────────┐
                                             │ Alert Triggered?│
                                             └─────────┬───────┘
                                                      │
                                         ┌────────────┴─────────────┐
                                         │                          │
                                         ▼                          ▼
                               ┌─────────────────┐        ┌─────────────────┐
                               │   NO ALERT      │        │ ALERT TRIGGERED │
                               │   Continue      │        │                 │
                               │   Monitoring    │        │ • Log Alert     │
                               └─────────────────┘        │ • Run Callbacks │
                                                         │ • Set Cooldown  │
                                                         └─────────┬───────┘
                                                                   │
                                                                   ▼
                                                         ┌─────────────────┐
                                                         │ Trigger Trading │
                                                         │ Decision        │
                                                         └─────────────────┘
```

### Decision Flow (AI Brain)
```
┌─────────────────┐
│ Market Data     │
│ (50 periods)    │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐
│ Technical       │────▶│ Prompt       │
│ Indicators      │     │ Engineering  │
│                 │     │              │
│ • SMA 20/50/200 │     │ • Context    │
│ • RSI 14        │     │ • Risk Rules │
│ • MACD          │     │ • Strategy   │
│ • Volume        │     │ • Market     │
└─────────────────┘     │   Conditions │
                        └──────┬───────┘
                               │
                               ▼
┌─────────────────┐     ┌──────────────┐
│ Claude API      │────▶│ Response     │
│                 │     │ Parsing      │
│ • Claude 3.5    │     │              │
│   Sonnet        │     │ • Extract    │
│ • Max Tokens    │     │   Signal     │
│ • Temperature   │     │ • Parse JSON │
└─────────────────┘     │ • Validate   │
                        └──────┬───────┘
                               │
                               ▼
┌─────────────────┐
│ TradingSignal   │
│                 │
│ • BUY/SELL/HOLD │
│ • Confidence    │
│ • Reasoning     │
│ • Entry Price   │
│ • Stop Loss     │
│ • Target        │
└─────────────────┘
```

### Risk Management Flow
```
┌─────────────────┐
│ Trading Signal  │
│ from AI         │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐
│ Position Size   │────▶│ Trade        │
│ Calculation     │     │ Validation   │
│                 │     │              │
│ • Capital * 2%  │     │ • Capital    │
│ • Stop Distance │     │   Available  │
│ • Min/Max Size  │     │ • Position   │
└─────────────────┘     │   Limits     │
                        │ • R:R Ratio  │
                        └──────┬───────┘
                               │
                  ┌────────────┴─────────────┐
                  │                          │
                  ▼                          ▼
        ┌─────────────────┐        ┌─────────────────┐
        │   APPROVED      │        │   REJECTED      │
        │   Trade         │        │   Log Reason    │
        └─────────┬───────┘        └─────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ Update Signal   │
        │ with Risk       │
        │ Parameters      │
        │                 │
        │ • Final Size    │
        │ • Adjusted SL   │
        │ • Slippage      │
        └─────────────────┘
```

### Trade Execution Flow
```
┌─────────────────┐
│ Validated       │
│ Trading Signal  │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐
│ Paper Trader    │────▶│ Position     │
│                 │     │ Tracking     │
│ • Commission    │     │              │
│ • Slippage      │     │ • Open       │
│ • Capital Mgmt  │     │ • Closed     │
└─────────┬───────┘     │ • P&L        │
          │             └──────────────┘
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Trade Record    │────▶│ Performance  │────▶│ Reporting       │
│                 │     │ Tracking     │     │                 │
│ • Entry/Exit    │     │              │     │ • Win Rate      │
│ • P&L           │     │ • Drawdown   │     │ • Sharpe Ratio  │
│ • Metadata      │     │ • Returns    │     │ • Risk Metrics  │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

## PART 3: DATA PIPELINE

### Real-Time Data Flow
1. **Collection**: DataCollector fetches from Zerodha API every 5 minutes
2. **Validation**: DataValidator checks price/volume sanity
3. **Storage**: DatabaseManager saves to SQLite with indicators
4. **Caching**: MemoryCache provides fast access to recent data
5. **Processing**: IndicatorEngine calculates technical indicators

### Historical Data Flow  
1. **Batch Collection**: collect_historical_data.py fetches historical candles
2. **Processing**: Same validation and indicator pipeline as real-time
3. **Storage**: Unified database schema with real-time data
4. **Simulation**: historical_simulator.py replays data chronologically

## PART 4: DECISION PIPELINE

### Information Flow to AI
```
Raw Market Data
      ↓
Technical Indicators (SMA, RSI, MACD, Volume)
      ↓  
Market Context (price changes, trends, support/resistance)
      ↓
Risk Context (capital, position limits, risk tolerance)
      ↓
Strategy Context (swing trading, market hours, symbols)
      ↓
Formatted Prompt (JSON structure, clear instructions)
      ↓
Claude API Call
      ↓
JSON Response Parsing
      ↓
Trading Signal (BUY/SELL/HOLD + parameters)
```

### Decision Quality Control
1. **Confidence Threshold**: Signals below 60% confidence become HOLD
2. **JSON Validation**: Malformed responses default to HOLD
3. **Risk Validation**: Risk manager can reject AI signals
4. **Position Limits**: Max position size and capital allocation enforced
5. **Market Hours**: Only trade during market hours (unless test mode)

## PART 5: MONITORING AND FEEDBACK

### System Monitoring
- **Data Quality**: Validation failures, missing data, stale prices
- **API Health**: Response times, error rates, rate limiting
- **Trading Performance**: P&L tracking, win rates, drawdown
- **Resource Usage**: Database size, memory usage, API quotas

### Feedback Loops
- **Decision History**: All AI decisions logged for analysis
- **Performance Attribution**: Track which signals lead to profits/losses
- **Data Quality Metrics**: Monitor indicator calculation success rates
- **Risk Metrics**: Track actual vs intended risk per trade

## PART 6: ERROR HANDLING AND RECOVERY

### Fault Tolerance
1. **API Failures**: Automatic fallback to mock data
2. **Database Issues**: Retry logic and connection pooling
3. **AI Failures**: Default to HOLD signal, log errors
4. **Validation Failures**: Skip corrupted data, continue processing
5. **Network Issues**: Exponential backoff for API calls

### Data Integrity
- **UPSERT Operations**: Handle duplicate timestamps gracefully
- **Transaction Management**: Atomic operations for consistency
- **Backup Strategy**: WAL mode for SQLite reliability
- **Validation Logging**: Track all data quality issues

## PART 7: ✅ CURRENT SYSTEM ARCHITECTURE

### Core Module Dependencies
```
apps/trader.py (Main Entry Point)
├── src/core/ai_brain.py ✅
│   ├── src/core/prompt_builder.py ✅
│   ├── src/interfaces.py ✅
│   └── src/utils/logger.py ✅
├── src/data_collector.py ✅
│   ├── src/data/apis.py ✅
│   ├── src/data/cache.py ✅
│   ├── src/data/database.py ✅
│   └── src/core/indicator_engine.py ✅
├── src/core/paper_trader.py ✅
│   ├── src/interfaces.py ✅
│   └── src/core/trading_modes.py ✅
├── src/core/risk_manager.py ✅
├── src/alerts/alert_engine.py ✅ NEW
│   └── src/alerts/rules.py ✅ NEW
└── src/data/config.py ✅
    └── src/data/stock_registry.py ✅
```

### Application Suite
```
apps/
├── trader.py ✅        (Main AI trading system)
├── backtest.py ✅      (Historical testing) 
├── monitor.py ✅       (System monitoring)
├── data_collector.py ✅ (Data management)
└── health_check.py ✅   (System diagnostics)
```

### External Dependencies
```
Production:
├── anthropic ✅           (Claude 3.5 Sonnet API)
├── kiteconnect ✅         (Zerodha API) 
├── pandas/numpy ✅        (Data processing)
├── sqlite3 ✅             (Database)
└── Standard library ✅    (datetime, json, etc.)

Development & Testing:
├── pytest ✅              (Testing framework)
├── unittest.mock ✅       (Test mocking)
└── argparse ✅            (CLI interfaces)
```

### ✅ System Status Summary
**Architecture**: Well-structured with clear separation of concerns  
**Alert System**: Fully operational with 4 alert types  
**Testing**: 100% test pass rate (39 tests)  
**Health Monitoring**: Comprehensive system diagnostics  
**Documentation**: Up-to-date and synchronized  
**Scalability**: Event-driven architecture ready for expansion