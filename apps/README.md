# 📱 Applications Directory

**Executable applications for the Claude AI Trading System**  
**Purpose**: User-facing applications for trading, backtesting, monitoring, and data collection  
**Target Users**: Traders, analysts, system administrators  

---

## 🎯 Applications Overview

This directory contains the main executable applications that users interact with. Each application is designed for specific trading system functions and can be run independently.

```
apps/
├── trader.py          ← Main trading application (live/paper trading)
├── backtest.py        ← Historical backtesting engine
├── data_collector.py  ← Data collection and management utility
├── monitor.py         ← System monitoring and dashboard
└── health_check.py    ← System health verification tool
```

---

## 🚀 trader.py - Main Trading Application

**Purpose**: Core trading system orchestrator with Claude AI integration  
**Use Case**: Live trading, paper trading, alert-driven trading  

### Features
- **Live Trading Mode**: Real-time market analysis and trade execution  
  ⚠️ **SAFETY**: Requires user confirmation and live data sources only  
- **Paper Trading Mode**: Risk-free simulation with real or mock data
- **Alert-Driven Mode**: Event-driven trading with 80% efficiency improvement
- **Paper Trading**: Safe simulation environment for testing strategies
- **Performance Tracking**: Real-time portfolio monitoring and reporting
- **Risk Management**: Integrated position sizing and safety controls

### Usage
```bash
# Run with default settings (paper trading)
python apps/trader.py

# Interactive mode with configuration options
python apps/trader.py --interactive

# Run specific number of cycles
python apps/trader.py --cycles 50

# Enable alert-driven mode (recommended)
python apps/trader.py --mode alert
```

### Configuration Required
```bash
# .env file requirements
ANTHROPIC_API_KEY=your_claude_api_key
ZERODHA_API_KEY=your_zerodha_key        # Optional: for live data
ZERODHA_ACCESS_TOKEN=your_access_token  # Optional: for live data
INITIAL_CAPITAL=10000                   # Starting capital
```

### Output
- **Real-time console output**: Trading decisions and performance
- **Log files**: Detailed logging in `data/logs/claude_trader.log`
- **Performance reports**: JSON reports saved to `data/reports/`
- **Position tracking**: Current holdings and P&L

---

## 📊 backtest.py - Historical Backtesting

**Purpose**: Historical simulation for strategy validation  
**Use Case**: Strategy testing, parameter optimization, performance analysis  

### Features
- **Historical Data Replay**: Chronological simulation of past market conditions
- **Claude AI Integration**: Test AI decisions on historical data
- **Performance Analysis**: Comprehensive backtesting metrics
- **Speed Control**: Configurable simulation speed (1x to 100x)
- **Strategy Comparison**: Compare different AI models and parameters

### Usage
```bash
# Interactive backtesting with date selection
python apps/backtest.py

# Quick backtest on last 7 days
python apps/backtest.py --period 7d --speed 10x

# Full system backtest
python apps/backtest.py --start 2024-01-01 --end 2024-12-31 --speed 50x
```

### Backtesting Options
1. **Last 3 days** (recommended for quick tests)
2. **Last week** (comprehensive recent performance)
3. **Last month** (longer-term validation)
4. **Custom date range** (specific period testing)
5. **All available data** (full historical analysis)

### Output
- **Performance Metrics**: Win rate, Sharpe ratio, max drawdown
- **Trade Log**: Detailed record of all simulated trades
- **Comparison Report**: Performance vs buy-and-hold baseline
- **Saved Results**: JSON files with complete backtesting data

---

## 📡 data_collector.py - Data Management

**Purpose**: Market data collection and database management  
**Use Case**: Data acquisition, database maintenance, historical data collection  

### Features
- **Multi-Source Data**: Zerodha API with Mock fallback
- **Automated Collection**: Scheduled data gathering for all symbols
- **Data Validation**: Quality checks and error handling
- **Database Optimization**: Automatic indexing and cleanup
- **Historical Backfill**: Collect missing historical data

### Usage
```bash
# Collect current data for all symbols
python apps/data_collector.py

# Collect specific date range
python apps/data_collector.py --start 2024-01-01 --end 2024-01-31

# Collect specific symbols only
python apps/data_collector.py --symbols RELIANCE,INFY,TCS

# Maintenance mode (cleanup and optimize)
python apps/data_collector.py --maintenance
```

### Data Collection Process
1. **Symbol Validation**: Verify symbols from stock registry
2. **API Connection**: Connect to Zerodha or fallback to Mock
3. **Data Retrieval**: Fetch OHLCV data with retry logic
4. **Quality Validation**: Check for data completeness and accuracy
5. **Database Storage**: Store with automatic duplicate handling
6. **Indicator Calculation**: Compute technical indicators
7. **Performance Logging**: Track collection success rates

### Output
- **Database Updates**: SQLite database with price and indicator data
- **Collection Reports**: Success/failure statistics
- **Data Quality Logs**: Validation results and error tracking
- **Performance Metrics**: Collection speed and API usage stats

---

## 📈 monitor.py - System Monitoring

**Purpose**: Real-time system monitoring and performance dashboard  
**Use Case**: System health monitoring, performance tracking, data quality oversight  

### Features
- **System Dashboard**: Real-time overview of system status
- **Data Quality Monitoring**: Check data completeness and freshness
- **Performance Metrics**: Track system performance and efficiency
- **Alert Status**: Monitor alert system health and activity
- **Database Health**: Check database size, performance, and integrity

### Usage
```bash
# Display comprehensive dashboard
python apps/monitor.py

# Continuous monitoring mode
python apps/monitor.py --continuous

# Generate system health report
python apps/monitor.py --report

# Monitor specific component
python apps/monitor.py --component alerts
```

### Monitoring Categories
1. **System Health**: Overall system status and uptime
2. **Data Quality**: Data freshness, completeness, accuracy
3. **Trading Performance**: Win rates, returns, risk metrics
4. **API Status**: External API availability and response times
5. **Database Status**: Storage usage, query performance, optimization
6. **Alert System**: Alert frequency, response times, effectiveness

### Dashboard Features
- **Real-time Updates**: Live system status refresh
- **Color-coded Status**: Green/Yellow/Red status indicators
- **Trend Analysis**: Historical performance trends
- **Alert Notifications**: System alerts and warnings
- **Resource Usage**: CPU, memory, disk usage monitoring

---

## 🔍 health_check.py - System Health Verification

**Purpose**: Comprehensive system health verification and diagnostics  
**Use Case**: System validation, troubleshooting, deployment verification  

### Features
- **Component Validation**: Test all system components individually
- **Configuration Check**: Verify all settings and environment variables
- **API Connectivity**: Test external API connections
- **Database Integrity**: Validate database structure and data
- **File System Check**: Verify required files and permissions

### Usage
```bash
# Run complete system health check
python apps/health_check.py

# Quick health check (essential components only)
python apps/health_check.py --quick

# Detailed diagnostic mode
python apps/health_check.py --detailed

# Check specific component
python apps/health_check.py --component database
```

### Health Check Categories
1. **Configuration**: Environment variables and settings validation
2. **File Structure**: Required files and directory permissions
3. **Database**: Schema validation and data integrity
4. **API Connections**: External service connectivity
5. **Import Dependencies**: Python module import verification
6. **System Resources**: Available memory, disk space, permissions

### Health Check Results
- **✅ PASS**: Component functioning correctly
- **⚠️ WARNING**: Component working but with issues
- **❌ FAIL**: Component not functioning, needs attention
- **📋 INFO**: Additional information and recommendations

---

## 🔧 Common Usage Patterns

### **Daily Trading Workflow**
```bash
# 1. Check system health
python apps/health_check.py

# 2. Update data
python apps/data_collector.py

# 3. Start trading (alert mode recommended)
python apps/trader.py --mode alert

# 4. Monitor performance
python apps/monitor.py --continuous
```

### **Strategy Development Workflow**
```bash
# 1. Collect historical data
python apps/data_collector.py --start 2024-01-01

# 2. Run backtests with different parameters
python apps/backtest.py --period 30d

# 3. Analyze results and optimize
python apps/monitor.py --report

# 4. Test with paper trading
python apps/trader.py --cycles 10
```

### **System Maintenance Workflow**
```bash
# 1. Full system health check
python apps/health_check.py --detailed

# 2. Database maintenance
python apps/data_collector.py --maintenance

# 3. Performance optimization
python optimize_system.py

# 4. Verify system functionality
python apps/trader.py --cycles 1
```

---

## 📊 Application Performance

| **Application** | **Typical Runtime** | **Memory Usage** | **CPU Usage** | **Disk I/O** |
|----------------|-------------------|------------------|---------------|--------------|
| **trader.py** | Continuous | 50-100 MB | Low-Medium | Low |
| **backtest.py** | 5-60 minutes | 100-200 MB | Medium-High | Medium |
| **data_collector.py** | 1-5 minutes | 30-50 MB | Low | High |
| **monitor.py** | Continuous | 20-40 MB | Low | Low |
| **health_check.py** | 10-30 seconds | 20-30 MB | Low | Low |

---

## 🚨 Troubleshooting

### **Common Issues and Solutions**

#### **trader.py Issues**
- **No trading signals**: Check AI API key and configuration
- **Data collection errors**: Verify API connectivity and symbols
- **Performance issues**: Enable alert mode for efficiency
- **Risk management blocks trades**: Review risk parameters in config

#### **backtest.py Issues**
- **No historical data**: Run data collector first
- **Slow performance**: Increase speed multiplier
- **Memory errors**: Reduce date range or symbols
- **Incomplete results**: Check for missing data periods

#### **data_collector.py Issues**
- **API failures**: Check API keys and network connectivity
- **Database errors**: Run health check and optimize database
- **Missing data**: Verify symbol names and date ranges
- **Slow collection**: Check API rate limits and system resources

#### **monitor.py Issues**
- **Dashboard not updating**: Check system permissions
- **Missing metrics**: Verify data collector is running
- **Performance warnings**: Run system optimization
- **Connection errors**: Check database and API status

---

## 🚨 Trading Mode Safety System

**CRITICAL**: This system includes comprehensive safeguards to prevent financial losses from data source errors.

### **Safety Modes**
- **📝 Paper Trading (Default)**: Safe simulation mode - allows any data source including mock data
- **💰 Live Trading**: Real money mode - requires user confirmation and live data sources only  
- **🔍 Backtest**: Historical simulation - uses historical data for analysis

### **Live Trading Safeguards**
1. **🛡️ Mock Data Prevention**: Automatically blocks fake/mock data in live trading mode
2. **🔐 User Confirmation Required**: Explicit "I UNDERSTAND THE RISKS" confirmation needed
3. **📡 Live Data Validation**: Only allows authenticated live data sources (Zerodha API)
4. **⚠️ API Failure Protection**: Prevents initialization if no live APIs available

### **How to Use Safely**
```bash
# Safe: Paper trading (default)
python apps/trader.py

# Safe: Explicit paper mode
TRADING_MODE=paper python apps/trader.py  

# ⚠️  LIVE MONEY: Requires confirmation
TRADING_MODE=live python apps/trader.py
```

**⚠️ WARNING**: Never disable safety checks when trading with real money.

---

## 📋 Configuration Files Used

### **All Applications Use:**
- **`.env`**: Environment variables and API keys
- **`src/data/config.py`**: System configuration constants
- **`instruments.csv`**: Zerodha symbol mapping (if using live data)

### **Application-Specific Configs:**
- **trader.py**: Trading parameters, risk settings, capital limits
- **backtest.py**: Simulation settings, speed controls, date ranges
- **data_collector.py**: Collection schedules, data sources, validation rules
- **monitor.py**: Dashboard refresh rates, alert thresholds, display options

---

## 🔗 Related Documentation

- **[System Architecture](../SYSTEM_ARCHITECTURE.md)**: Technical architecture overview
- **[Source Code](../src/README.md)**: Module documentation
- **[Configuration Guide](../src/data/README.md)**: Setup and configuration
- **[Testing Guide](../tests/README.md)**: Testing these applications
- **[API Documentation](../docs/api/)**: Detailed API reference

---

**🎯 Quick Start: Run `python apps/trader.py` to start paper trading, or `python apps/health_check.py` to verify system readiness.**