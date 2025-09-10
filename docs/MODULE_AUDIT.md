# MODULE AUDIT REPORT
*Generated: 2025-01-10*

## PART 1: SRC/ DIRECTORY MODULES

### Module: config.py
**Purpose**: Configuration settings and environment management for the trading bot
**Key Classes/Functions**:
- `get_trading_symbols()` - Get symbols for specific trading strategy
- `switch_trading_strategy()` - Switch to different trading strategy
- `get_symbol_info()` - Get detailed information about trading symbol
- `validate_config()` - Validate configuration parameters
- `is_market_hours()` - Check if market is currently open
- `calculate_position_size()` - Calculate position size based on risk

**Dependencies**:
- External packages: os, dotenv, datetime, pytz
- Internal modules: src.stock_registry

**Used By**: All modules (central configuration)
**Database Tables Used**: None
**API Endpoints**: None
**Configuration Used**: All environment variables, trading parameters, risk settings
**Status**: ACTIVE
**Issues Found**:
- Hardcoded fallback symbols if stock_registry unavailable
- Multiple strategy switching mechanisms could be consolidated

### Module: data_collector.py
**Purpose**: Fetch and store market data from various sources with fallback support
**Key Classes/Functions**:
- `DataCollector` - Main orchestrator for data collection
- `DatabaseManager` - Handle database operations 
- `DataValidator` - Validate market data quality
- `MemoryCache` - Simple memory cache for recent data

**Dependencies**:
- External packages: sqlite3, pandas, numpy, datetime
- Internal modules: src.utils.logger, src.config, src.interfaces, src.data_sources, src.indicator_engine

**Used By**: claude_trader.py, collect_historical_data.py, historical_simulator.py
**Database Tables Used**: price_data, indicators, daily_stats, data_quality_log
**API Endpoints**: None (uses data sources)
**Configuration Used**: SYMBOLS, DB_PATH, MARKET_TIMEZONE, caching TTL
**Status**: ACTIVE
**Issues Found**:
- Complex dependencies between components
- Database connection not properly handled in all error paths
- Cache TTL hardcoded (should be configurable)

### Module: ai_brain.py
**Purpose**: Claude API integration for AI-powered trading decisions
**Key Classes/Functions**:
- `ClaudeAI` - Main AI decision maker using Anthropic Claude
- `SimpleRuleBasedModel` - Alternative rule-based model for comparison
- `_create_analysis_prompt()` - Create detailed prompts for Claude
- `_parse_claude_response()` - Parse JSON responses from Claude

**Dependencies**:
- External packages: anthropic, pandas, json, datetime
- Internal modules: src.interfaces, src.config, src.utils.logger, src.risk_manager

**Used By**: claude_trader.py, historical_simulator.py
**Database Tables Used**: None
**API Endpoints**: Anthropic Claude API
**Configuration Used**: ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, risk parameters
**Status**: ACTIVE
**Issues Found**:
- Complex prompt engineering with many hardcoded values
- Error handling for Claude API failures needs improvement
- Decision history logging could be more structured

### Module: data_sources.py
**Purpose**: Concrete implementations of market data APIs using interfaces
**Key Classes/Functions**:
- `ZerodhaAPI` - Zerodha Kite Connect integration
- `MockAPI` - Mock data for testing during market closure

**Dependencies**:
- External packages: kiteconnect, pandas, requests, yfinance
- Internal modules: src.interfaces, src.utils.logger

**Used By**: src.data_collector
**Database Tables Used**: None (reads instruments.csv)
**API Endpoints**: Zerodha Kite Connect API
**Configuration Used**: ZERODHA_API_KEY, ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN
**Status**: ACTIVE
**Issues Found**:
- YFinance import present but not used (dead import)
- Error handling could be more specific
- Token mapping depends on external instruments.csv file

### Module: interfaces.py
**Purpose**: Abstract base classes and core data structures for standardized interfaces
**Key Classes/Functions**:
- `MarketData` - Standard market data structure
- `TradingSignal` - Trading signal data structure
- `BaseMarketDataAPI` - Abstract base for market data sources
- `BaseDecisionModel` - Abstract base for trading models
- `BaseRiskManager` - Abstract base for risk management
- `BaseTradingExecutor` - Abstract base for trade execution

**Dependencies**:
- External packages: abc, typing, datetime, dataclasses, pandas

**Used By**: All modules (interface definitions)
**Database Tables Used**: None
**API Endpoints**: None
**Configuration Used**: None
**Status**: ACTIVE
**Issues Found**: None (well-designed interface module)

### Module: indicator_engine.py
**Purpose**: Unified technical indicator calculations for the trading bot
**Key Classes/Functions**:
- `compute_indicators()` - Main indicator computation function
- `calculate_all_indicators()` - Calculate all available indicators
- `calculate_sma()`, `calculate_rsi()`, `calculate_macd()` - Specific indicators
- Legacy functions: `_rsi()`, `_macd()` for backward compatibility

**Dependencies**:
- External packages: pandas, numpy, warnings

**Used By**: src.data_collector, historical_simulator.py
**Database Tables Used**: None
**API Endpoints**: None
**Configuration Used**: None
**Status**: ACTIVE
**Issues Found**:
- Legacy functions should be deprecated properly
- Warning suppression might hide legitimate issues
- Limited indicator set (could add more indicators)

### Module: risk_manager.py
**Purpose**: Centralized risk management for trading operations
**Key Classes/Functions**:
- `SimpleRiskManager` - Main risk management implementation
- `RiskParameters` - Container for risk calculations
- `calculate_position_size()` - Core position sizing logic
- `validate_trade()` - Trade validation against risk rules

**Dependencies**:
- External packages: typing, dataclasses, logging
- Internal modules: src.interfaces, src.config

**Used By**: src.ai_brain, claude_trader.py, historical_simulator.py
**Database Tables Used**: None
**API Endpoints**: None
**Configuration Used**: MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, commission settings
**Status**: ACTIVE
**Issues Found**:
- Risk-reward ratio warning threshold hardcoded
- Portfolio risk calculation incomplete
- Some advanced risk management features marked as "Future enhancements"

### Module: stock_registry.py
**Purpose**: Centralized stock management with sector organization and metadata
**Key Classes/Functions**:
- `StockRegistry` - Main registry class
- `StockInfo` - Data structure for stock information
- Enums: `Sector`, `MarketCap`, `LiquidityRating`
- Portfolio functions: `get_conservative_portfolio()`, `get_swing_trading_symbols()`

**Dependencies**:
- External packages: typing, dataclasses, enum, json, os

**Used By**: src.config
**Database Tables Used**: None (can save/load from JSON)
**API Endpoints**: None
**Configuration Used**: None (self-contained)
**Status**: ACTIVE
**Issues Found**:
- Stock data hardcoded (should be in external data file)
- Limited to large-cap stocks mainly
- No integration with live market cap data

### Module: paper_trader.py
**Purpose**: Simulated trading system for testing strategies without real money
**Key Classes/Functions**:
- `PaperTrader` - Main paper trading implementation
- `PaperTrade` - Data structure for trade records
- `execute_trade()` - Execute simulated trades
- `generate_performance_report()` - Comprehensive performance metrics

**Dependencies**:
- External packages: json, datetime, pandas
- Internal modules: src.interfaces, src.config, src.utils.logger

**Used By**: claude_trader.py, historical_simulator.py
**Database Tables Used**: None (logs to JSON files)
**API Endpoints**: None
**Configuration Used**: INITIAL_CAPITAL, commission/slippage settings, position limits
**Status**: ACTIVE
**Issues Found**:
- Trade validation logic partially duplicated with risk_manager
- Performance metrics could be more comprehensive
- Position updates could be optimized

## PART 2: SRC/UTILS/ DIRECTORY

### Module: logger.py
**Purpose**: Centralized logging configuration for trading bot
**Key Classes/Functions**:
- `setup_logger()` - Configure logger with file and console handlers
- `ColoredFormatter` - Custom formatter for console colors
- `TradingLogger` - Specialized logger for structured trading logs

**Dependencies**:
- External packages: logging, os, datetime

**Used By**: All modules for logging
**Database Tables Used**: None
**API Endpoints**: None
**Configuration Used**: LOG_LEVEL, log file paths
**Status**: ACTIVE
**Issues Found**: None (well-implemented logging system)

## PART 3: ROOT LEVEL MODULES

### Module: claude_trader.py
**Purpose**: Main Claude-driven trading system orchestrator
**Key Classes/Functions**:
- `ClaudeTrader` - Main orchestrator class
- `run_trading_cycle()` - Execute complete trading cycle
- `run_continuous_trading()` - Run multiple cycles
- `get_performance_report()` - Generate comprehensive reports

**Dependencies**:
- External packages: json, datetime
- Internal modules: src.ai_brain, src.risk_manager, src.paper_trader, src.data_collector, src.indicator_engine, src.config, src.utils.logger

**Used By**: Entry point for main trading system
**Database Tables Used**: Via data_collector
**API Endpoints**: Via ai_brain (Claude API)
**Configuration Used**: SYMBOLS, INITIAL_CAPITAL, market hours
**Status**: ACTIVE
**Issues Found**:
- Complex orchestration logic could be split into smaller methods
- Error recovery mechanisms could be improved
- Performance tracking could be more detailed

### Module: collect_historical_data.py
**Purpose**: Unified historical data collection from Zerodha API
**Key Classes/Functions**:
- `compute_date_range()` - Calculate date ranges for collection
- `main()` - CLI interface for historical collection

**Dependencies**:
- External packages: argparse, logging, datetime, pathlib
- Internal modules: src.data_collector, src.data_sources, src.config

**Used By**: Standalone script
**Database Tables Used**: Via data_collector
**API Endpoints**: Zerodha historical data API
**Configuration Used**: SYMBOLS from config
**Status**: ACTIVE
**Issues Found**:
- Limited date range options
- No resume capability for interrupted collections
- Rate limiting could be more sophisticated

### Module: historical_simulator.py
**Purpose**: Simulate trading system on historical data for backtesting
**Key Classes/Functions**:
- `HistoricalSimulator` - Main simulation engine
- `HistoricalDataProvider` - Provides data in chronological order
- `SimulationDataCollector` - Simulates DataCollector for historical data

**Dependencies**:
- External packages: sqlite3, pandas, numpy, datetime, logging
- Internal modules: src.config, src.data_collector, src.indicator_engine, src.interfaces, src.utils.logger

**Used By**: Standalone script for backtesting
**Database Tables Used**: price_data (read-only)
**API Endpoints**: None (uses historical data)
**Configuration Used**: SYMBOLS, DB_PATH, INITIAL_CAPITAL
**Status**: ACTIVE
**Issues Found**:
- Complex initialization with multiple try-catch blocks
- Error handling for missing components needs improvement
- Memory usage could be optimized for large datasets

### Module: monitor.py
**Purpose**: Monitor data collection status and quality
**Key Classes/Functions**:
- `DataMonitor` - Main monitoring class
- `display_dashboard()` - Show comprehensive dashboard
- `check_alerts()` - Check for conditions needing attention

**Dependencies**:
- External packages: sqlite3, pandas, datetime, tabulate
- Internal modules: src.config

**Used By**: Standalone monitoring script
**Database Tables Used**: price_data, data_quality_log, indicators
**API Endpoints**: None
**Configuration Used**: DB_PATH, SYMBOLS
**Status**: ACTIVE
**Issues Found**:
- Hardcoded alert thresholds
- Dashboard could be more interactive
- No real-time monitoring capability

## PART 4: TEST MODULES

### Module: test_ai_brain.py
**Purpose**: Test script for AI Brain module functionality
**Key Functions**:
- `test_with_real_data()` - Test with actual market data
- `test_all_symbols()` - Test AI decisions across multiple symbols

**Dependencies**:
- External modules: Test imports from main modules
**Status**: ACTIVE
**Issues Found**:
- Hardcoded test parameters
- Limited test coverage
- No automated assertions

### Module: test_data_collector.py
**Purpose**: Test script for data collector functionality
**Key Functions**:
- `test_single_symbol()`, `test_all_symbols()` - Data collection tests
- `test_indicators()`, `test_cache()` - Specific feature tests

**Dependencies**:
- External modules: Test imports from main modules
**Status**: ACTIVE
**Issues Found**:
- Tests require manual verification
- No automated test suite
- Limited error condition testing

## PART 5: SCRIPTS

### Module: generate_zerodha_token.py
**Purpose**: Automatically generate Zerodha access token through OAuth flow
**Key Functions**:
- `catch_token()` - Flask endpoint to capture OAuth token
- `main()` - Launch browser and handle token exchange

**Dependencies**:
- External packages: flask, kiteconnect, dotenv, webbrowser, pathlib

**Used By**: Standalone setup script
**Status**: ACTIVE
**Issues Found**:
- Flask server doesn't shut down automatically after token capture
- No error handling for network issues
- Hardcoded port number

## SUMMARY STATISTICS

**Total Modules Analyzed**: 16
- src/ modules: 8
- utils/ modules: 1  
- Root modules: 4
- Test modules: 2
- Script modules: 1

**Status Breakdown**:
- ACTIVE: 16
- PARTIALLY_USED: 0
- DEAD: 0

**Key Issues Identified**:
1. Hardcoded configuration values throughout codebase
2. Inconsistent error handling patterns
3. Some complex classes could be split into smaller components
4. Limited test coverage with manual verification
5. Some "Future enhancement" TODOs that should be prioritized
6. Database connections not always properly closed
7. API rate limiting could be more sophisticated