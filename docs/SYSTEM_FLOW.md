# TRADING SYSTEM FLOW ANALYSIS
*Generated: 2025-01-10*

## PART 1: ENTRY POINTS

The system has several entry points for different use cases:

### 1. claude_trader.py
**Purpose**: Main AI-driven trading system
**Entry**: `python claude_trader.py`
**Mode**: Continuous trading with AI decisions

### 2. collect_historical_data.py  
**Purpose**: Historical data collection
**Entry**: `python collect_historical_data.py [--period 1mo] [--interval 5m]`
**Mode**: One-time data collection

### 3. historical_simulator.py
**Purpose**: Backtesting on historical data
**Entry**: `python historical_simulator.py`
**Mode**: Simulation and backtesting

### 4. monitor.py
**Purpose**: Data quality monitoring
**Entry**: `python monitor.py`
**Mode**: Dashboard and alerting

### 5. Test Scripts
**Purpose**: System validation
**Entry**: `python tests/test_*.py`
**Mode**: Testing and validation

## PART 2: CORE SYSTEM FLOW

### Main Trading Flow (claude_trader.py)
```
┌─────────────────┐
│   SYSTEM START  │
│   ClaudeTrader  │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Initialize     │────▶│ DataCollector│────▶│  Database       │
│  Components     │     │ RiskManager  │     │  Setup          │
│                 │     │ AI Brain     │     │                 │
└─────────┬───────┘     │ Paper Trader │     └─────────────────┘
          │             └──────────────┘
          ▼
┌─────────────────┐
│ TRADING CYCLE   │
│ (Every 5 min)   │
└─────────┬───────┘
          │
          ▼
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃                    PER-SYMBOL PROCESSING                          ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
          │
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ 1. Data         │────▶│ 2. Calculate │────▶│ 3. AI Analysis  │
│ Collection      │     │ Indicators   │     │ (Claude)        │
└─────────────────┘     └──────────────┘     └─────────┬───────┘
                                                       │
                                                       ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ 6. Update       │◀────│ 5. Execute   │◀────│ 4. Risk         │
│ Positions       │     │ Trade        │     │ Validation      │
└─────────────────┘     └──────────────┘     └─────────────────┘
          │
          ▼
┌─────────────────┐
│  END CYCLE      │
│ (Wait 5 min)    │
└─────────────────┘
```

### Data Pipeline Flow
```
┌─────────────────┐
│   DATA SOURCES  │
│                 │
│ • ZerodhaAPI    │
│ • MockAPI       │ 
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐
│ DataCollector   │────▶│ DataValidator│
│                 │     │              │
│ • MemoryCache   │     │ • Price      │
│ • Fallback      │     │   Validation │
│ • Rate Limiting │     │ • Volume     │
└─────────┬───────┘     │   Checks     │
          │             └──────┬───────┘
          ▼                    │
┌─────────────────┐            │
│ MarketData      │◀───────────┘
│ (Validated)     │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ DatabaseManager │────▶│ Indicator    │────▶│   Database      │
│                 │     │ Engine       │     │                 │
│ • UPSERT Logic  │     │              │     │ • price_data    │
│ • Error Handling│     │ • SMA        │     │ • indicators    │
│ • WAL Mode      │     │ • RSI        │     │ • daily_stats   │
└─────────────────┘     │ • MACD       │     └─────────────────┘
                        └──────────────┘
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
│ • GPT-4 Model   │     │              │
│ • Max Tokens    │     │ • Extract    │
│ • Temperature   │     │   Signal     │
│ • JSON Format   │     │ • Parse JSON │
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

## PART 7: DEPENDENCIES GRAPH

```
claude_trader.py
├── src/ai_brain.py
│   ├── src/interfaces.py
│   ├── src/config.py  
│   ├── src/risk_manager.py
│   └── src/utils/logger.py
├── src/data_collector.py
│   ├── src/interfaces.py
│   ├── src/data_sources.py
│   │   └── src/utils/logger.py
│   ├── src/indicator_engine.py
│   ├── src/config.py
│   └── src/utils/logger.py
├── src/paper_trader.py
│   ├── src/interfaces.py
│   ├── src/config.py
│   └── src/utils/logger.py
├── src/risk_manager.py
│   ├── src/interfaces.py
│   └── src/config.py
└── src/config.py
    └── src/stock_registry.py

External Dependencies:
├── anthropic (Claude AI)
├── kiteconnect (Zerodha API) 
├── pandas/numpy (Data processing)
├── sqlite3 (Database)
├── flask (Token generation)
└── Standard library modules
```

This flow analysis reveals a well-architected system with clear separation of concerns, proper abstraction layers, and robust error handling. The main areas for improvement are in configuration management, test coverage, and advanced risk management features.