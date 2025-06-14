# Trading Bot - NSE Swing Trading with AI

An AI-powered trading bot for NSE (Indian stock market) swing trading, using Claude API for decision-making and multiple data sources with automatic fallback.

## 🎯 Project Overview

- **Market**: NSE (National Stock Exchange of India)
- **Trading Style**: Swing trading (2-5 day holds)
- **Initial Capital**: ₹1,000
- **Risk Management**: 2% per trade, 20% max drawdown
- **AI**: Claude API for trading decisions
- **Data Sources**: Dhan API (primary), Yahoo Finance, Twelve Data (fallbacks)

## 🏗️ Architecture

The system uses a modular architecture with abstract base classes for extensibility:

```
Data Sources (Dhan/yfinance/TwelveData)
    ↓
Data Collector (with fallback chain)
    ↓
Database (SQLite → TimescaleDB)
    ↓
Indicator Engine
    ↓
AI Brain (Claude API)
    ↓
Paper Trader
    ↓
Risk Manager
    ↓
Order Executor (Future: Zerodha)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11.9 (managed via pyenv)
- Linux (tested on Ubuntu/Arch)
- Anthropic API key
- Dhan API key (optional, falls back to yfinance)

### Installation

```bash
# Clone repository
git clone [your-repo-url]
cd trading-tiding

# Set Python version
pyenv local 3.11.9

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.template .env
# Edit .env and add your API keys:
# - ANTHROPIC_API_KEY
# - DHAN_API_KEY (optional)
```

### First Run

```bash
# Run setup script
chmod +x setup_data_collection.sh
./setup_data_collection.sh

# Test data collection
python test_data_collector.py

# Start automated collection (during market hours)
python scheduler.py

# Monitor system
python monitor.py
```

## 📁 Project Structure

```
trading-tiding/
├── src/                    # Core source code
│   ├── data_collector.py   # Data orchestration
│   ├── interfaces.py       # Abstract base classes
│   ├── data_sources.py     # API implementations
│   ├── config.py           # Configuration
│   ├── ai_brain.py         # Claude integration (WIP)
│   ├── paper_trader.py     # Paper trading (WIP)
│   └── utils/
│       └── logger.py       # Logging utilities
├── data/                   # Data storage
│   ├── market_data.db      # SQLite database
│   ├── logs/               # Application logs
│   └── reports/            # Daily reports
├── docs/                   # Documentation
│   ├── architecture/       # System design
│   ├── decisions_day_*.md  # Daily decision logs
│   └── research/           # Research documents
├── scheduler.py            # Automated data collection
├── monitor.py              # System monitoring
├── test_data_collector.py  # Test suite
└── PROJECT_TOC.md          # Master navigation

## 📊 Features

### Implemented ✅
- [x] Multi-source data collection with fallback
- [x] Abstract base class architecture
- [x] 5-minute interval data collection
- [x] Technical indicator calculation (SMA, RSI, MACD)
- [x] Data validation and quality checks
- [x] SQLite storage with TimescaleDB migration path
- [x] Memory caching for performance
- [x] Comprehensive logging system
- [x] Monitoring dashboard
- [x] Automated scheduler

### In Progress 🚧
- [ ] AI Brain (Claude integration)
- [ ] Paper trading system
- [ ] Dhan API implementation

### Planned 📅
- [ ] Zerodha integration
- [ ] Advanced indicators (TA-Lib)
- [ ] Backtesting system
- [ ] Risk management module
- [ ] Web dashboard
- [ ] Cloud deployment (Azure)

## 🔧 Configuration

Key parameters in `src/config.py`:
- **Trading symbols**: Top 10 NSE stocks (RELIANCE, TCS, INFY, etc.)
- **Risk parameters**: 2% per trade, 20% max drawdown
- **Market hours**: 9:15 AM - 3:30 PM IST
- **Data intervals**: 5 minutes

## 📈 Trading Strategy

Current implementation:
- Collects OHLCV data every 5 minutes
- Calculates technical indicators
- Stores for AI analysis (pending)
- Paper trades based on AI decisions (pending)

## 🧪 Testing

```bash
# Run all tests
python test_data_collector.py

# Test specific component
python test_data_collector.py
# Choose option 1-5

# Check logs
tail -f data/logs/data_collector.log
```

## 📊 Data Storage

- **Daily**: ~3.5MB for all symbols
- **Monthly**: ~100MB
- **Yearly**: ~1.2GB
- **Current DB**: SQLite (single file)
- **Future**: TimescaleDB (optimized for time-series)

## 🔒 Security

- API keys stored in environment variables
- No sensitive data in logs
- Git-ignored data directories
- Validated inputs

## 📝 Development Workflow

1. **Morning**: Check system health, review logs
2. **Market hours**: Monitor data collection
3. **End of day**: Review performance, plan improvements
4. **Documentation**: Update decision logs, TOC

## ⚠️ Risk Disclaimer

This is experimental software for educational purposes. Paper trade extensively before considering live trading. The developers are not responsible for any financial losses.

## 🤝 Contributing

This is a personal project, but suggestions are welcome via issues.

## 📄 License

MIT License - See LICENSE file for details

---

**Current Status**: Day 3 - Data collection complete, building AI integration
**Next Goal**: Paper trading system by end of Week 1