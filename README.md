# 🤖 Claude AI Trading Bot - Production Ready

An **AI-powered trading system** that uses Claude API to autonomously manage capital, analyze markets, and execute trades with professional risk management on the NSE (Indian stock market).

## 🎯 **What This System Does**

- **🧠 AI-Driven Decisions**: Claude analyzes market data and makes intelligent trading decisions
- **💰 Capital Management**: Automatically manages ₹10,000+ with professional position sizing
- **🛡️ Risk Protection**: Built-in risk management prevents overexposure and losses
- **📊 Performance Tracking**: Comprehensive analytics and trade performance monitoring
- **🎯 Multi-Strategy**: Conservative, swing trading, diversified, and tech-focused portfolios
- **📈 Backtesting**: Historical simulation to validate AI performance before live trading

---

## 🚀 **Quick Start**

### **Prerequisites**
- Python 3.11.9 (managed via pyenv)
- Anthropic API key (Claude)
- Zerodha API credentials (for live trading)

### **Installation**
```bash
# Clone and setup
git clone [your-repo-url]
cd trading-bot
pyenv local 3.11.9
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Add your API keys to .env:
# ANTHROPIC_API_KEY=your-claude-api-key
# ZERODHA_API_KEY=your-zerodha-key
```

### **Verify System Health**
```bash
python system_check.py
# Expected: All components operational ✅
```

### **Test Without API Costs**
```bash
python tests/test_trading_session.py
# Expected: Complete system validation with mock data ✅
```

### **Start Claude Trading**
```bash
# Option 1: Historical backtesting (validate AI performance)
python historical_simulator.py

# Option 2: Live AI trading (requires API credits)
python claude_trader.py
```

---

## 🏗️ **System Architecture**

```
Market Data → Claude AI Analysis → Risk Management → Trade Execution → Performance Tracking
     ↓              ↓                    ↓               ↓              ↓
  Real-time     Intelligent         Position         Paper/Live      Analytics
   OHLCV       Trading Signals      Sizing &         Trading         & Reports
  + Indicators                      Validation       Simulation
```

### **Core Components**

| Component | Purpose | Status |
|-----------|---------|--------|
| **Claude AI Brain** | Market analysis & trading decisions | ✅ Production Ready |
| **Risk Manager** | Position sizing & capital protection | ✅ Production Ready |
| **Paper Trader** | Trade simulation & performance tracking | ✅ Production Ready |
| **Data Pipeline** | Market data collection & indicators | ✅ Production Ready |
| **Stock Registry** | 24 stocks across 8 sectors with strategies | ✅ Production Ready |
| **Historical Simulator** | Backtesting & AI validation | ✅ Production Ready |

---

## 📊 **Trading Capabilities**

### **AI-Powered Analysis**
- **Technical Indicators**: RSI, MACD, SMAs, volume analysis
- **Market Context**: Comprehensive prompt engineering for Claude
- **Decision Confidence**: Confidence scoring and reasoning tracking
- **Multi-Timeframe**: 5-minute data with historical context

### **Risk Management**
- **Position Sizing**: Kelly Criterion-inspired calculations
- **Stop Losses**: Dynamic or fixed (1.5% default)
- **Capital Protection**: Maximum 20% per position
- **Risk-Reward**: Minimum 1.5:1 ratio enforcement

### **Portfolio Management**
- **24 NSE Stocks**: Large-cap focus across 8 sectors
- **Strategy Options**: Conservative, Swing, Diversified, Tech Focus
- **Sector Allocation**: Banking, Technology, Energy, FMCG, Telecom, etc.
- **Performance Monitoring**: Real-time P&L, drawdown, win rates

---

## 💰 **Capital Management**

### **Default Configuration**
- **Initial Capital**: ₹10,000 (configurable)
- **Risk Per Trade**: 1.5% (₹150 max loss per trade)
- **Max Position Size**: 20% of capital (₹2,000 per stock)
- **Stop Loss**: 1.5% (dynamic based on AI analysis)
- **Target Profit**: 3% (2:1 risk-reward ratio)

### **Professional Features**
- **Automatic Position Sizing**: Based on volatility and risk tolerance
- **Portfolio Diversification**: Cross-sector allocation limits
- **Drawdown Protection**: Maximum 15% portfolio drawdown
- **Commission Handling**: Realistic cost simulation

---

## 🧪 **Testing & Validation**

### **Pre-Trading Validation**
```bash
# 1. System Health Check (30 seconds)
python system_check.py

# 2. Integration Test - FREE (2 minutes)
python tests/test_trading_session.py

# 3. Historical Performance (10 minutes)
python historical_simulator.py
```

### **Comprehensive Test Suite**
- **Integration Testing**: Complete system without API costs
- **Component Testing**: Individual module validation
- **Historical Simulation**: AI performance on past data
- **Performance Analytics**: Detailed metrics and reporting

---

## 📈 **Trading Strategies**

### **Available Portfolios**

| Strategy | Stocks | Focus | Risk Level |
|----------|--------|-------|------------|
| **Conservative** | HDFCBANK, ICICIBANK, TCS, INFY, SBIN | Large-cap, defensive | Low |
| **Swing Trading** | RELIANCE, SBIN, ONGC, INFY, ICICIBANK | High liquidity, volatility | Medium |
| **Diversified** | Cross-sector representation | Balanced exposure | Medium |
| **Tech Focus** | TCS, INFY, HCLTECH, WIPRO, TECHM | Technology sector | Medium-High |

### **Strategy Selection**
```bash
# Configure via environment variable
export TRADING_STRATEGY=conservative  # or swing, diversified, tech_focus
python claude_trader.py
```

---

## 🎛️ **Configuration**

### **Key Settings** (`src/config.py`)
```python
# Trading Parameters
INITIAL_CAPITAL = 10000        # Starting capital
MAX_RISK_PER_TRADE = 0.015     # 1.5% risk per trade
STOP_LOSS_PERCENT = 0.015      # 1.5% stop loss
TAKE_PROFIT_PERCENT = 0.03     # 3% target profit

# AI Settings
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
CLAUDE_MAX_TOKENS = 1000
CLAUDE_TEMPERATURE = 0.3

# Market Hours
MARKET_OPEN = "09:15"          # IST
MARKET_CLOSE = "15:30"         # IST
```

### **Stock Universe** (`src/stock_registry.py`)
24 carefully selected NSE stocks across 8 sectors with liquidity ratings and market cap classifications.

---

## 📊 **Performance Monitoring**

### **Real-Time Metrics**
- **Capital Tracking**: Current vs initial capital
- **Return Calculation**: Percentage returns with benchmarking
- **Risk Metrics**: Maximum drawdown, Sharpe ratio
- **Trade Analytics**: Win rate, average holding period
- **AI Performance**: Decision confidence, reasoning quality

### **Reporting**
```bash
# Generate performance report
python claude_trader.py --report

# View trading logs
tail -f data/logs/claude_trader.log

# Access decision database
sqlite3 data/market_data.sqlite
```

---

## 🔧 **Advanced Features**

### **Historical Backtesting**
- **Time-Based Simulation**: Replay historical market conditions
- **AI Decision Validation**: Test Claude's performance on past data
- **Strategy Comparison**: Compare different approaches
- **Performance Metrics**: Comprehensive analytics

### **Risk Management**
- **Position Validation**: Multi-layer trade approval process
- **Portfolio Limits**: Sector and concentration limits
- **Dynamic Stops**: ATR-based stop loss calculations
- **Performance Tracking**: Real-time risk monitoring

### **Data Pipeline**
- **Unified Collection**: Live and historical data through same validation
- **Quality Control**: Data validation and error handling
- **Indicator Calculation**: Technical analysis with caching
- **Database Management**: Efficient SQLite storage with optimization

---

## 🎯 **Use Cases**

### **Individual Traders**
- **AI-Assisted Trading**: Let Claude analyze markets while you oversee
- **Risk-Managed Growth**: Professional position sizing for capital preservation
- **Learning Tool**: Understand AI decision-making process
- **Strategy Testing**: Validate approaches before real money

### **Educational**
- **AI Trading Research**: Study machine learning in financial markets
- **Risk Management**: Learn professional position sizing techniques
- **Market Analysis**: Understand technical indicator usage
- **System Design**: Study production trading system architecture

---

## 📝 **API Usage & Costs**

### **Anthropic Claude API**
- **Model**: Claude-3.5-Sonnet-20241022
- **Usage**: ~500-1000 tokens per analysis
- **Cost**: ~$0.01-0.02 per trading decision
- **Optimization**: Smart triggers reduce unnecessary API calls

### **Cost Optimization Features**
- **Smart Triggers**: Only analyze on significant market changes
- **Decision Caching**: Avoid redundant analyses
- **Batch Processing**: Efficient multi-symbol analysis
- **Usage Tracking**: Monitor daily API costs

---

## 🛡️ **Security & Safety**

### **Risk Controls**
- **Capital Limits**: Hard limits on position sizes and risk
- **Stop Loss Enforcement**: Automatic loss cutting
- **Drawdown Protection**: System-wide risk monitoring
- **Trade Validation**: Multi-layer approval process

### **Data Security**
- **API Key Management**: Environment variable storage
- **Log Sanitization**: No sensitive data in logs
- **Local Storage**: All data stored locally
- **Error Handling**: Graceful failure management

---

## 🤝 **Contributing**

This is a personal trading system, but architectural suggestions are welcome via issues.

### **Development Workflow**
1. **Test Changes**: `python tests/test_trading_session.py`
2. **Validate System**: `python system_check.py`
3. **Check Integration**: Run historical simulation
4. **Document Updates**: Update README and TOC

---

## 📄 **License**

MIT License - See LICENSE file for details

---

## 🎯 **Quick Commands**

```bash
# Daily Usage
python system_check.py                    # Verify system health
python tests/test_trading_session.py      # Test without API costs
python claude_trader.py                   # Start AI trading
python historical_simulator.py            # Backtest AI performance

# Monitoring
python monitor.py                          # Data quality dashboard
tail -f data/logs/claude_trader.log        # Live trading logs
sqlite3 data/market_data.sqlite            # Database access

# Testing
python tests/test_ai_brain.py              # Test Claude integration
python tests/test_data_collector.py        # Test data pipeline
python tests/test_anthropic_setup.py       # Verify API setup
```

---

## 🎊 **System Status: Production Ready**

✅ **Architecture**: Clean, modular, maintainable  
✅ **AI Integration**: Claude making informed trading decisions  
✅ **Risk Management**: Professional capital protection  
✅ **Performance Tracking**: Comprehensive analytics  
✅ **Testing**: Complete validation suite  
✅ **Documentation**: Professional-grade documentation

**Ready for autonomous AI trading with proper risk management.**

---

*Built with Claude AI for intelligent market analysis and decision-making.*
