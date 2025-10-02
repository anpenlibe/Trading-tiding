# 🤖 AI Trading System

**AI-Powered Trading Bot for NSE Indian Stock Market**

Automated trading system using AI (Claude/Gemini) for market analysis and decision making with comprehensive risk management.

---

## 🚀 Quick Start

### **1. Installation**
```bash
# Clone and setup
git clone <repository>
cd trading-tiding
pip install -r requirements.txt

# Configure environment
cp .env.template .env
```

### **2. Configuration (.env file)**
```bash
# Required: AI API Key (supports both Claude and Gemini)
GEMINI_API_KEY=your_gemini_api_key     # Google AI Studio
ANTHROPIC_API_KEY=your_claude_api_key  # Anthropic Console

# Gemini model selection
GEMINI_MODEL=gemini-1.5-flash          # Fast for testing
# GEMINI_MODEL=gemini-2.0-flash-exp    # For production

# Optional: Live NSE data (otherwise uses realistic mock data)
ZERODHA_API_KEY=your_zerodha_key        # From Kite Connect dashboard
ZERODHA_API_SECRET=your_zerodha_secret  # From Kite Connect dashboard

# Trading parameters (optional - good defaults provided)
INITIAL_CAPITAL=10000
MAX_RISK_PER_TRADE=0.015  # 1.5% risk per trade
```

### **3. Generate Zerodha Access Token (Optional - For Live Data)**
If you want live NSE market data:

```bash
# Automated token generation (handles OAuth flow)
python scripts/generate_zerodha_token.py

# The script will:
# 1. Open browser to Zerodha login
# 2. Handle OAuth authentication
# 3. Save token to your .env automatically
# 4. Verify token works with test data fetch
```

**📝 Note**: Zerodha tokens expire daily and need renewal. Re-run the script when you see "Unauthorized" errors.

### **4. Run Your First Trading Session**
```bash
# Quick system check
python apps/health_check.py

# Start paper trading (safe simulation)
python apps/trader.py

# Or run backtesting to see historical performance
python apps/backtest.py
```

---

## 📱 Applications

| **Application** | **Purpose** | **Command** |
|-----------------|-------------|-------------|
| **`trader.py`** | Main trading system | `python apps/trader.py` |
| **`backtest.py`** | Historical simulation | `python apps/backtest.py` |
| **`data_collector.py`** | Data management | `python apps/data_collector.py` |
| **`monitor.py`** | System monitoring | `python apps/monitor.py` |
| **`health_check.py`** | System validation | `python apps/health_check.py` |

### **Daily Usage Examples**
```bash
# Morning: Check system health and update data
python apps/health_check.py && python apps/data_collector.py

# Start trading in alert mode (recommended - more efficient)
python apps/trader.py --mode alert

# Monitor performance in another terminal
python apps/monitor.py --continuous
```

---

## 🚨 Critical Safety Features

**This system includes comprehensive safeguards to prevent financial losses:**

🛡️ **Mock Data Protection**: Automatically prevents fake data in live trading mode
🔐 **Live Trading Confirmation**: Requires explicit user confirmation for real money trading
📡 **Data Source Validation**: Only authenticated live data sources allowed in live mode
⚠️ **API Failure Protection**: Prevents trading if no live data APIs are available

**⚠️ IMPORTANT**: Always start with paper trading mode to test the system safely.

```bash
# Safe: Paper trading (default - no real money risk)
python apps/trader.py

# ⚠️  Real Money: Requires explicit confirmation
TRADING_MODE=live python apps/trader.py
```

---

## 🧠 How The AI Trading Works

### **1. Market Analysis**
- **Real-time data**: Collects OHLCV data from NSE stocks
- **Technical indicators**: Calculates RSI, MACD, SMA automatically
- **Market context**: Builds comprehensive market analysis prompts

### **2. AI Decision Making**
- **Intelligent analysis**: Claude AI or Gemini analyzes market conditions (configurable)
- **Confidence scoring**: Each decision includes confidence level (0-100%)
- **Detailed reasoning**: AI explains why it made each decision
- **Risk awareness**: Considers portfolio and risk factors

### **3. Risk Management**
- **Position sizing**: Kelly Criterion-inspired calculations
- **Stop losses**: Automatic stop loss (configurable)
- **Portfolio limits**: Max position per stock and sector
- **Risk per trade**: Maximum 1.5% capital risk per trade

### **4. Trade Execution**
- **Realistic simulation**: Includes slippage and commissions
- **Performance tracking**: Real-time P&L, win rates, Sharpe ratio
- **Position management**: Automatic stop loss and take profit execution

---

## ⚡ Event-Driven Alert System

Instead of checking markets every 5 minutes, the alert system monitors continuously but only triggers AI analysis when significant events occur.

### **Alert Types**
- **📈 Price Alerts**: Significant price movements
- **📊 RSI Extremes**: Overbought (>70) or oversold (<30)
- **📈 Volume Spikes**: 2x+ normal volume activity
- **🔄 MACD Crossovers**: Bullish/bearish signal crossovers

### **Efficiency Gains**
- **80% fewer API calls**: Only analyze when markets move significantly
- **Cost reduction**: Significant reduction in API costs
- **Faster response**: <1 minute from alert to action
- **Better decisions**: Focus on meaningful market events only

```bash
# Enable alert mode (recommended)
python apps/trader.py --mode alert
```

---

## 🏗️ System Architecture

```
📱 Applications Layer     → apps/          (Trading, Backtesting, Monitoring)
🧠 Business Logic Layer  → src/core/      (AI, Risk, Trading, Analysis)
📊 Data Layer           → src/data/       (APIs, Database, Configuration)
⚡ Alert System         → src/alerts/     (Event Detection, Rules, Monitoring)
🤖 AI Components        → src/ai/         (Prompt Engineering)
📈 Monitoring          → src/monitoring/ (Performance, Error Tracking)
🔧 Utilities           → src/utils/      (Logging, Database Optimization)
🧪 Testing Suite       → tests/          (Automated tests)
```

---

## 💰 Supported Stocks

### **20 NSE Stocks Across 8 Sectors**
- **Banking**: HDFC Bank, ICICI Bank, State Bank, Axis Bank, Kotak Bank, IndusInd
- **Technology**: TCS, Infosys, Wipro, HCL Tech
- **Energy**: Reliance Industries, ONGC, BPCL
- **Automobile**: Maruti Suzuki, Tata Motors, Bajaj Auto
- **FMCG**: Hindustan Unilever, ITC
- **Pharma**: Sun Pharma, Dr Reddy's
- **Telecom**: Bharti Airtel
- **Metals**: Tata Steel

### **Portfolio Strategies**
- **Conservative**: Large-cap, high-liquidity stocks
- **Swing Trading**: Medium volatility stocks
- **Diversified**: Cross-sector spread
- **Tech Focused**: Technology and growth stocks

---

## 🧪 Testing & Quality

### **Test Suite**
```bash
# Run complete test suite
python run_tests.py

# Run with coverage report
python run_tests.py --coverage

# Quick essential tests only
python run_tests.py --quick
```

---

## 🔧 Advanced Configuration

### **Trading Parameters**
```bash
# Risk Management
MAX_RISK_PER_TRADE=0.015     # 1.5% max risk per trade
STOP_LOSS_PERCENT=0.05       # 5% stop loss
TAKE_PROFIT_PERCENT=0.08     # 8% take profit

# Position Limits
MAX_POSITIONS=8              # Max open positions
MAX_POSITION_SIZE=0.25       # 25% max per stock

# Technical Indicators
RSI_PERIOD=14               # RSI calculation period
RSI_OVERBOUGHT=70          # RSI overbought threshold
RSI_OVERSOLD=30            # RSI oversold threshold
```

### **Alert System Tuning**
```bash
# Alert Sensitivity
PRICE_ALERT_THRESHOLD=0.02   # 2% price movement
VOLUME_SPIKE_MULTIPLIER=2.0  # 2x volume for spike
ALERT_COOLDOWN_MINUTES=30    # Prevent alert spam

# System Performance
CACHE_TTL_SECONDS=300        # 5-minute data cache
DB_OPTIMIZATION_ENABLED=true # Auto database optimization
```

---

## 📚 Documentation

### **Technical Documentation**
- **[docs/SYSTEM_FLOW.md](./docs/SYSTEM_FLOW.md)** - System flow and architecture
- **[docs/ALERT_BASED_TRADING_SYSTEM.md](./docs/ALERT_BASED_TRADING_SYSTEM.md)** - Alert system details
- **[docs/api/](./docs/api/)** - API documentation for all modules
- **[docs/research/](./docs/research/)** - Research and reference materials

### **System Analysis**
- **[COMPREHENSIVE_CLAIMS_TO_VERIFY.md](./COMPREHENSIVE_CLAIMS_TO_VERIFY.md)** - System testing and verification results
- **[system_analysis/reports/ai_position_enforcement_proposal.md](./system_analysis/reports/ai_position_enforcement_proposal.md)** - Feature proposals

---

## 🚨 Troubleshooting

### **Common Issues**
| **Problem** | **Solution** | **Details** |
|-------------|-------------|-------------|
| **"No API key"** | Add `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` to `.env` | Get from anthropic.com or Google AI Studio |
| **"Unauthorized" / "Token expired"** | Run `python scripts/generate_zerodha_token.py` | Zerodha tokens expire daily |
| **"No trading signals"** | Check internet connection | System needs AI API access |
| **"Tests failing"** | Run `python apps/health_check.py` | Comprehensive system diagnosis |
| **"Poor performance"** | Enable alert mode | `python apps/trader.py --mode alert` |
| **"Data collection errors"** | Use mock data fallback | System works without live data APIs |

### **Getting Help**
```bash
# System health check
python apps/health_check.py

# View system status
python apps/monitor.py

# Check logs
tail -f data/logs/claude_trader.log
```

---

## 🔒 Security & Compliance

- **Environment-based secrets**: All API keys in `.env` file (never committed)
- **No hardcoded credentials**: Zero secrets in source code
- **Comprehensive error handling**: Graceful failure management
- **Automatic fallbacks**: System continues operating during failures
- **Data validation**: Multi-level data quality and integrity checks
- **Trading mode safety**: Prevents accidental live trading with test data

---

## 📞 Support

### **Getting Started Issues**
1. **Check**: `python apps/health_check.py`
2. **Verify**: `.env` file has `ANTHROPIC_API_KEY` or `GEMINI_API_KEY`
3. **Test**: `python apps/trader.py --cycles 1`
4. **Monitor**: `python apps/monitor.py`

### **System Requirements**
- Python 3.8+
- 100MB+ free disk space
- Internet connection for API access
- (Optional) Zerodha Kite Connect account for live data

---

**Built with Claude AI / Gemini for intelligent market analysis**
