# Trading Bot Source Code Documentation

## Overview
This directory contains the core modules for the NSE swing trading bot. The system uses abstract base classes for extensibility and implements a robust multi-source data collection system with automatic fallback.

## Architecture

### Design Patterns
1. **Strategy Pattern**: Abstract base classes for swappable implementations
2. **Chain of Responsibility**: Fallback chain for data sources
3. **Observer Pattern**: Event-driven updates (future)
4. **Singleton Pattern**: Single instances of managers

### Module Structure

```
src/
├── interfaces.py       # Abstract base classes
├── data_sources.py     # Concrete API implementations
├── data_collector.py   # Data orchestration
├── config.py          # Configuration
├── ai_brain.py        # AI integration (WIP)
├── paper_trader.py    # Paper trading (WIP)
└── utils/
    └── logger.py      # Logging utilities
```

## Core Modules

### 📋 interfaces.py
**Purpose**: Defines abstract base classes for standardized interfaces

**Key Classes**:
- `BaseMarketDataAPI`: Interface for all data sources
- `BaseDecisionModel`: Interface for AI/rule-based decisions
- `BaseRiskManager`: Interface for risk management
- `BaseTradingExecutor`: Interface for trade execution

**Usage**:
```python
from src.interfaces import BaseMarketDataAPI, MarketData

class NewDataSource(BaseMarketDataAPI):
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        # Implementation
        pass
    
    def is_available(self) -> bool:
        # Check if configured
        pass
```

### 📊 data_sources.py
**Purpose**: Concrete implementations of market data APIs

**Implemented APIs**:
1. **DhanAPI**: Primary source (token ready, implementation pending)
2. **YFinanceAPI**: Reliable fallback, currently active
3. **TwelveDataAPI**: Secondary fallback (needs API key)
4. **MockAPI**: For testing without market connection

**Adding New APIs**:
```python
class AlphaVantageAPI(BaseMarketDataAPI):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_KEY')
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        # Your implementation
        pass
    
    def is_available(self) -> bool:
        return bool(self.api_key)
```

### 📈 data_collector.py
**Purpose**: Orchestrates data collection with automatic fallback

**Key Features**:
- Multi-source data fetching with fallback chain
- 5-minute interval collection during market hours
- Technical indicator calculation
- Data validation and quality checks
- Efficient caching system

**Data Collection Flow**:
```
Market Hours (9:15 AM - 3:30 PM)
│
├─► Every 5 minutes:
│   ├─► Check cache (5-min TTL)
│   ├─► Try Dhan API
│   ├─► Fallback to yfinance
│   ├─► Fallback to Twelve Data
│   ├─► Validate data
│   ├─► Calculate indicators
│   ├─► Store in SQLite
│   └─► Update cache
│
└─► End of Day:
    ├─► Generate daily summary
    ├─► Archive to Parquet (future)
    └─► Clean up old data
```

**Collected Data**:
- **Raw Data**: OHLCV (Open, High, Low, Close, Volume)
- **Calculated Indicators**: 
  - Moving Averages (20, 50, 200)
  - RSI (14 period)
  - MACD (12, 26, 9)
  - Volume Average (20 period)
  - Price change percentage

### 🧠 ai_brain.py (Work in Progress)
**Purpose**: Analyzes market data using Claude API to generate trading signals

**Planned Features**:
- Claude API integration
- Structured prompt generation
- Signal generation (BUY/SELL/HOLD)
- Confidence scoring
- Decision logging

**Expected Interface**:
```python
class ClaudeAI(BaseDecisionModel):
    def analyze(self, market_data: pd.DataFrame, 
                indicators: Dict[str, float]) -> Dict[str, Any]:
        # Returns: {
        #     "signal": "BUY",
        #     "confidence": 0.85,
        #     "reasoning": "...",
        #     "stop_loss": 2800,
        #     "target": 2950
        # }
```

### 💼 paper_trader.py (Work in Progress)
**Purpose**: Simulates trades without real money for strategy validation

**Planned Features**:
- Virtual portfolio management
- Trade execution simulation
- P&L tracking
- Performance metrics
- Risk management rules

### ⚙️ config.py
**Purpose**: Central configuration for the entire system

**Key Settings**:
- API credentials (loaded from .env)
- Trading parameters (risk, capital)
- Stock symbols (10 NSE stocks)
- Market hours
- Database paths
- Indicator parameters

### 🔧 utils/logger.py
**Purpose**: Centralized logging with structured output

**Features**:
- Colored console output
- File rotation (10MB max)
- Separate error log
- Structured logging for trading events
- Performance tracking

## Database Schema

### SQLite Tables (Current)
```sql
-- Price data (every 5 minutes)
CREATE TABLE price_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, timestamp)
);

-- Technical indicators
CREATE TABLE indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    sma_20 REAL,
    sma_50 REAL,
    sma_200 REAL,
    rsi_14 REAL,
    macd REAL,
    macd_signal REAL,
    macd_histogram REAL,
    volume_avg_20 REAL,
    price_change_pct REAL,
    UNIQUE(symbol, timestamp)
);

-- Daily summaries
CREATE TABLE daily_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    vwap REAL,
    trades_count INTEGER,
    UNIQUE(symbol, date)
);

-- Data quality log
CREATE TABLE data_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT,
    issue_type TEXT,
    description TEXT,
    severity TEXT
);
```

### Future: TimescaleDB Migration
The schema is designed for easy migration to TimescaleDB:
- Compatible column types
- Time-series optimized structure
- Minimal code changes required

## Storage Estimates
- **Daily**: ~3.5MB (all stocks)
- **Monthly**: ~100MB
- **Yearly**: ~1.2GB

## Monitored Stocks
1. RELIANCE - Reliance Industries
2. TCS - Tata Consultancy Services
3. INFY - Infosys
4. HDFC - HDFC Bank
5. ICICIBANK - ICICI Bank
6. SBIN - State Bank of India
7. BHARTIARTL - Bharti Airtel
8. ITC - ITC Limited
9. KOTAKBANK - Kotak Mahindra Bank
10. LT - Larsen & Toubro

## API Integration Status

### Active
- **yfinance**: Working, primary data source currently

### Ready
- **Dhan API**: Token configured, awaiting implementation

### Configured
- **Twelve Data**: Needs API key

### Planned
- **Zerodha**: Future integration for live trading

## Error Handling

### Circuit Breaker Pattern
- Prevents cascade failures
- Automatic recovery testing
- Fallback to cache if all APIs fail

### Data Validation
- Price sanity checks (±20% limits)
- Volume verification (minimum 100)
- Timestamp validation
- OHLC relationship checks

### Logging Levels
- **INFO**: Normal operations
- **WARNING**: Recoverable issues
- **ERROR**: Failures requiring attention
- **DEBUG**: Detailed troubleshooting

## Performance Optimization

### Caching
- 5-minute TTL for market data
- Memory-based for fast access
- Automatic cleanup of expired entries

### Database
- WAL mode enabled
- Indexed queries
- Batch inserts

### API Calls
- Parallel fetching (future)
- Rate limiting
- Connection pooling

## Development Guidelines

### Adding New Features
1. Define interface in `interfaces.py`
2. Implement concrete class
3. Add tests
4. Update documentation

### Code Style
- Type hints for all functions
- Comprehensive docstrings
- Error handling with logging
- Follow PEP 8

### Testing
- Unit tests for each module
- Integration tests for workflows
- Mock APIs for offline testing

## Future Enhancements

### Phase 1 (Current)
✅ Basic data collection
✅ Abstract interfaces
✅ SQLite storage
✅ Simple indicators
✅ Memory cache

### Phase 2 (Next Week)
- [ ] AI Brain implementation
- [ ] Paper trading system
- [ ] Basic backtesting
- [ ] Performance analytics

### Phase 3 (Month 2)
- [ ] Advanced indicators
- [ ] Risk management
- [ ] Portfolio optimization
- [ ] TimescaleDB migration

### Phase 4 (Month 3+)
- [ ] Zerodha integration
- [ ] Live trading
- [ ] Web dashboard
- [ ] Cloud deployment