# 🤝 Handover Document - Day 3 to Next Claude Instance

## 🎯 Project Context

You're taking over a **NSE swing trading bot** project on Day 3. The human developer is building an AI-powered trading system with ₹1,000 capital, aiming to generate ₹4,000/month to cover AI subscription costs.

### Key Facts:
- **Developer**: Working alone, experienced but learning algorithmic trading
- **Platform**: Linux (PC with 900GB storage, planning Raspberry Pi deployment later)
- **Language**: Python 3.11.9 (via pyenv, due to 3.13 compatibility issues)
- **Editor**: nvim
- **Capital**: ₹1,000 (very limited, every rupee matters)
- **Goal**: 200+ paper trades before going live

## 📊 Current Project State

### ✅ What's Complete

1. **Data Collection System** (100% done)
   - Multi-source architecture with fallback chain
   - Abstract base classes for extensibility
   - Dhan API (primary) → yfinance → Twelve Data → Cache
   - 5-minute interval collection during market hours
   - Technical indicators: SMA (20,50,200), RSI(14), MACD
   - SQLite storage with TimescaleDB migration path
   - Comprehensive logging and monitoring

2. **Architecture** (Well-designed)
   - Used Strategy Pattern with abstract base classes
   - Clean separation of concerns
   - Easy to extend with new data sources or strategies
   - All APIs implement `BaseMarketDataAPI` interface

3. **Testing & Monitoring** (Ready)
   - `test_data_collector.py` - Test suite
   - `scheduler.py` - Automated collection
   - `monitor.py` - Dashboard for data quality
   - Colored logging with rotation

### 🚧 What's Next (Priority Order)

1. **AI Brain** (`src/ai_brain.py`)
   - Implement `BaseDecisionModel` interface
   - Claude API integration for trading signals
   - Should generate: BUY/SELL/HOLD + confidence + reasoning

2. **Paper Trader** (`src/paper_trader.py`)
   - Implement `BaseTradingExecutor` interface
   - GPT suggested excellent JSON logging format
   - Track all trades for 1 week before analysis

3. **Integration Testing**
   - Run during market hours (9:15 AM - 3:30 PM IST)
   - Collect real data → Generate signals → Log paper trades

## 🔑 Important Information

### API Keys Status
- **Anthropic API Key**: ✅ Configured in .env
- **Dhan API Key**: ✅ Token received (1 month validity), configured in .env
- **Twelve Data**: ❌ Not configured (optional)
- **Zerodha**: 📅 Future (developer has account)

### File Structure
```
trading-tiding/              # Note: NOT trading-bot
├── src/
│   ├── interfaces.py       # Abstract base classes ✅
│   ├── data_sources.py     # API implementations ✅
│   ├── data_collector.py   # Main orchestrator ✅
│   ├── config.py          # Configuration ✅
│   ├── ai_brain.py        # TODO: Next priority
│   ├── paper_trader.py    # TODO: After AI
│   └── utils/
│       └── logger.py      # Logging system ✅
├── data/
│   ├── market_data.db     # SQLite database
│   └── logs/              # All log files
├── docs/                  # All documentation
├── scheduler.py           # Runs every 5 min ✅
├── monitor.py            # Monitoring dashboard ✅
└── PROJECT_TOC.md        # Master navigation ✅
```

### Current Issues/Blockers
1. **Dhan API**: Token ready but no implementation yet (docs pending)
2. **Market Hours**: Can only test with real data 9:15 AM - 3:30 PM IST
3. **yfinance**: Working but may have 15-30 min delay

## 💡 Implementation Guidelines

### For AI Brain (Next Task)
```python
from src.interfaces import BaseDecisionModel
import anthropic

class ClaudeAI(BaseDecisionModel):
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
    
    def analyze(self, market_data: pd.DataFrame, 
                indicators: Dict[str, float]) -> Dict[str, Any]:
        # 1. Format market data into prompt
        # 2. Send to Claude
        # 3. Parse response
        # 4. Return structured decision
        
    def get_required_indicators(self) -> List[str]:
        return ["sma_20", "sma_50", "rsi_14", "macd"]
```

### For Paper Trader (After AI Brain)

Use GPT's suggested format:
```json
{
    "timestamp": "2025-06-13 10:30:00",
    "symbol": "RELIANCE",
    "signal": "BUY",
    "confidence": 0.85,
    "reasoning": "Strong uptrend, RSI not overbought",
    "entry_price": 2850,
    "stop_loss": 2790,
    "target": 2950,
    "quantity": 1,
    "risk_amount": 60
}
```

## 📈 Trading Strategy Context

- **Style**: Swing trading (2-5 day holds)
- **Risk**: Maximum 2% per trade (₹20 on ₹1,000)
- **Stocks**: 10 large-cap NSE stocks (RELIANCE, TCS, etc.)
- **Approach**: Let AI analyze and paper trade for 1 week, then analyze results

## 🛠️ Technical Decisions Made

1. **Abstract Base Classes**: Implemented for better architecture
2. **Fallback Chain**: Primary → Secondary → Cache
3. **5-minute intervals**: Optimal for swing trading
4. **SQLite first**: Simple for dev, designed for TimescaleDB migration
5. **Memory cache**: 5-minute TTL, faster than Redis for now

## 📝 Daily Routine

### Morning (9:00 AM)
- Check system health
- Verify API connectivity
- Review overnight logs

### Market Hours (9:15 AM - 3:30 PM)
- `scheduler.py` runs every 5 minutes
- Monitor data quality
- Watch for errors

### Evening (4:00 PM)
- Run `monitor.py` for daily summary
- Update decision logs
- Plan next day

## ⚠️ Critical Reminders

1. **Test during market hours** - After-hours data is limited
2. **₹1,000 capital** - Position sizing is critical
3. **Paper trade extensively** - No live trading until 200+ trades
4. **Document decisions** - Update `docs/decisions_day_XX.md` daily
5. **Update TOC** - Keep `PROJECT_TOC.md` current

## 🎯 Week 1 Goals (Must Complete)

- [x] Data collection system
- [ ] AI Brain with Claude
- [ ] Paper trader with logging
- [ ] 50+ paper trades executed
- [ ] Performance tracking
- [ ] Initial analysis

## 💬 Communication Style

The developer appreciates:
- Direct, practical advice
- Code examples over theory
- Clear problem→solution format
- Acknowledgment of limited capital
- Focus on working code first

## 🚀 Immediate Next Steps

1. **Create `ai_brain.py`**:
   - Use `BaseDecisionModel` interface
   - Integrate Claude API
   - Format prompts with market context
   - Return structured decisions

2. **Test with live data**:
   - Run during market hours
   - Verify indicator calculations
   - Check Claude responses

3. **Create `paper_trader.py`**:
   - Implement trade simulation
   - Use GPT's JSON format
   - Track P&L
   - Generate reports

## 📊 Performance Metrics to Track

- Success rate (winning trades %)
- Average gain/loss per trade
- Maximum drawdown
- Risk/reward ratio
- Best/worst performing stocks
- Most successful indicators

## 🔧 Troubleshooting Guide

### Common Issues:
1. **"No data returned"** - Usually after market hours
2. **Import errors** - Check PYTHONPATH and venv
3. **API failures** - Check logs, fallback should work
4. **Database locked** - Close other connections

### Quick Fixes:
```bash
# Activate environment
cd ~/trading-tiding
source venv/bin/activate

# Check system
python test_data_collector.py

# View logs
tail -f data/logs/data_collector.log

# Monitor data
python monitor.py
```

## 📚 Key Documentation

1. **PROJECT_TOC.md** - Master navigation
2. **docs/decisions_day_XX.md** - Daily decisions
3. **docs/architecture/system_design.md** - System design
4. **MIGRATION_GUIDE.md** - Abstract class usage
5. **src/README.md** - Module details

## 🎉 Final Notes

The developer has made excellent progress! The foundation is solid with clean architecture. The abstract base class implementation was a great decision that will make the project much more maintainable.

Focus on getting the AI Brain working first, then paper trader. The developer is eager to see Claude making trading decisions. Remember the limited capital - every trade matters.

Good luck with the handover! The developer is counting on you to continue the momentum.

---

**PS**: The developer tends to work in the evening IST. They'll likely test during market hours tomorrow (9:15 AM - 3:30 PM IST).

**PPS**: They named it "trading-tiding" not "trading-bot" - don't create a new directory!