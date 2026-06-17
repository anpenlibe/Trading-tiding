# Alert-Based Trading System — Design & Roadmap

**Purpose**: Design rationale and roadmap for the event-driven alert system.
This is a planning document: it mixes **what's built today** with **proposed
extensions**. Each section is labelled — treat anything under "Proposed" /
"Roadmap" as design intent, not shipped code.

> **Built today:** the `AlertEngine`, four rule types (`PriceCrossRule`,
> `RSIExtremeRule`, `VolumeSpikRule`, `MACDCrossRule`), cooldown + callbacks, and
> wiring in `apps/trader.py`. The default `trader.py` run still uses the polling
> `run_trading_cycle()`; the continuous event-driven loop is `run_alert_mode()`.

---

## 🎯 Goal

A polling loop runs AI analysis on every symbol every interval, regardless of
whether anything moved — most of those (paid or rate-limited) AI calls are
wasted on quiet markets. The alert system instead runs **cheap rule checks** on
incoming data and only fires the **expensive AI call** when a rule trips.

### Design goals
- **Event-driven**: AI analysis only on significant market events
- **Multiple signal types**: RSI, MACD, volume, price
- **Cooldown system**: prevents alert spam
- **Extensible**: easy to add new rule types

---

## 📊 Cost rationale (illustrative)

> These figures are **hypothetical projections** for a *paid* always-polling
> setup, used to motivate the event-driven design. The current bot runs on free
> tiers (Groq free tier, Yahoo/bundled data), so real spend is ~$0 — but the
> *waste* argument (analysing quiet markets) still holds, and matters once you
> hit rate limits or move to paid APIs.

### Illustrative cost of always-polling (paid APIs, monthly)
| Component | Usage | Cost |
|-----------|---------------|------|
| **Market Data API** | 13,200 calls | $66.00 |
| **AI API** | 19.8M tokens | $59.40 |
| **Total Monthly Cost** | - | **$125.40** |
| **Annual Cost** | - | **$1,504.80** |

### Usage Pattern (assumed)
- **Symbols**: 8 (RELIANCE, SBIN, ONGC, INFY, ICICIBANK, ITC, TATAMOTORS, AXISBANK)
- **Frequency**: Every 5 minutes during market hours
- **Market Hours**: 6.25 hours/day (9:15 AM - 3:30 PM IST)
- **Trading Days**: 22 days/month
- **Daily API Calls**: 600 (8 symbols × 75 intervals)

### Problem Impact
1. **High Testing Costs**: $396 for 6-month historical testing
2. **Scalability Issues**: Linear cost increase with more symbols
3. **Resource Waste**: API calls even when no action needed
4. **Budget Constraints**: Limits extensive backtesting capabilities

---

## 🏗️ ✅ Implemented Alert-Based Architecture

### Core Components

#### 1. Alert Engine ✅ IMPLEMENTED
**Module**: `src/alerts/alert_engine.py`
**Status**: Fully operational

**Implemented Classes**:
```python
class AlertEngine:
    - Manages alert rules and subscriptions
    - Evaluates conditions against market data
    - Dispatches alerts with callback system
    - Implements cooldown management

class AlertRule:
    - Base class for all alert types
    - Abstract interface for condition checking
    - Metadata generation for triggered alerts

class Alert:
    - Data structure for triggered alerts
    - Contains symbol, condition, threshold info
    - Includes priority and metadata
```

**Key Features**:
- ✅ Rule-based condition evaluation
- ✅ Cooldown system to prevent spam
- ✅ Callback registration for alert handling
- ✅ Comprehensive logging and metadata

#### 2. Alert Rules System ✅ IMPLEMENTED
**Module**: `src/alerts/rules.py`
**Status**: Core alert types operational

**Implemented Alert Types**:
```python
# ✅ Technical Indicator Alerts
- RSIExtremeRule: RSI overbought/oversold detection
- MACDCrossRule: MACD signal line crossovers
- VolumeSpikRule: Volume surge detection

# ✅ Price Movement Alerts  
- PriceCrossRule: Price threshold crossovers

# Enums and Types
- AlertType: PRICE_CROSS, RSI_EXTREME, VOLUME_SPIKE, MACD_CROSS
```

### Integration Status ✅ OPERATIONAL

#### Alert System Integration
The alert system is fully integrated and operational with:

**✅ Configuration Integration**
- Alert thresholds configured in `src/data/config.py`
- RSI overbought/oversold levels from RSI_OVERBOUGHT, RSI_OVERSOLD
- Volume analysis period from VOLUME_SMA_PERIOD
- Proper logging integration with centralized logger

**✅ System Health Integration**
- Alert system health checks in `apps/health_check.py`
- Import validation and functionality testing
- Error tracking and logging integration

---

## 🔄 Alert-Based Workflow

### 1. Setup Phase (One-time)
```
Historical Data Analysis
    ↓
Identify Alert Patterns
    ↓
Configure Alert Rules
    ↓
Set Thresholds & Subscriptions
    ↓
Initialize Alert Engine
```

### 2. Monitoring Phase (Continuous)
```
Monitor Market Conditions (using cached/historical data)
    ↓
Evaluate Alert Rules (low cost operation)
    ↓
Alert Triggered? 
    ├─ No: Continue monitoring
    └─ Yes: Proceed to Response Phase
```

### 3. Response Phase (On Alert)
```
Alert Triggered
    ↓
Fetch Fresh Market Data (API Call)
    ↓
Calculate Technical Indicators
    ↓
AI Analysis (provider fallback chain: Groq → Gemini → Claude) 
    ↓
Risk Assessment
    ↓
Trading Decision
    ↓
Execute Trade (if applicable)
    ↓
Update Portfolio & Alerts
```

---

## 📈 Cost-Benefit Analysis

### Current vs Alert-Based Comparison

| Metric | Current System | Alert-Based System | Improvement |
|--------|----------------|-------------------|-------------|
| **Monthly API Calls** | 13,200 | 1,500-3,000 | 77-89% reduction |
| **Monthly AI Calls** | 13,200 | 1,500-3,000 | 77-89% reduction |
| **Monthly Cost** | $125.40 | $15-30 | 76-88% reduction |
| **Annual Cost** | $1,504.80 | $180-360 | $1,144-1,324 savings |
| **Response Time** | 5 minutes | <1 minute | 5x faster |
| **Scalability** | Linear cost | Sub-linear cost | Much better |

### Alert Frequency Estimates
Based on typical market conditions:
- **RSI Alerts**: 2-4 per symbol per day
- **Price Gap Alerts**: 1-2 per symbol per day  
- **Volume Spike Alerts**: 1-3 per symbol per day
- **MACD Crossover Alerts**: 1-2 per symbol per day
- **Total Estimated**: 5-11 alerts per symbol per day
- **Monthly Total**: 880-1,936 alerts across 8 symbols

---

## 🛠️ Implementation Status

### Phase 1: Core Alert Infrastructure — built
**Status**: implemented and wired into `apps/trader.py` (not yet unit-tested)

**Modules**:
```
src/alerts/
├── __init__.py           Package structure
├── alert_engine.py       AlertEngine, AlertRule, Alert classes
└── rules.py              PriceCrossRule, RSIExtremeRule, VolumeSpikRule, MACDCrossRule
```

**✅ Integrated Features**:
- AlertEngine with rule evaluation system
- AlertRule base class with 4 concrete implementations
- Alert data structure with metadata support
- Comprehensive logging and cooldown management

### Phase 2: Testing
**Status**: Automated tests for the alert system are not yet implemented
(`tests/` is currently empty). Alert behaviour is exercised manually via
`apps/health_check.py` and the trading apps.

### Phase 3: System Integration — partial
**Status**: wired into the trader; health check only does an import smoke-test

- `apps/trader.py` arms rules and routes fired alerts to `_analyze_and_trade`
- `apps/health_check.py` imports `src.alerts.alert_engine` (import check only —
  no behavioural alert validation yet)

---

## 🎯 Alert Rule Specifications — PROPOSED (roadmap)

> ⚠️ **Not implemented.** The classes below (`RSI_OverboughtAlert`,
> `MACD_BullishCrossover`, `PriceGapAlert`, `DrawdownAlert`, etc.) are a *design
> sketch* of richer rules. The shipped rules are the four in
> [`src/alerts/rules.py`](../src/alerts/rules.py): `PriceCrossRule`,
> `RSIExtremeRule`, `VolumeSpikRule`, `MACDCrossRule`. Treat this section as the
> wishlist for where the rule system could go.

### Technical Indicator Alerts

#### RSI-Based Alerts
```python
class RSI_OverboughtAlert(AlertRule):
    threshold: float = 70.0
    min_duration: int = 2  # Must stay overbought for 2 periods
    cooldown: int = 60     # 60 minutes between alerts
    
class RSI_OversoldAlert(AlertRule):
    threshold: float = 30.0
    min_duration: int = 2
    cooldown: int = 60
```

#### MACD-Based Alerts
```python
class MACD_BullishCrossover(AlertRule):
    signal_sensitivity: float = 0.1
    min_macd_value: float = -5.0  # Avoid false signals at extremes
    
class MACD_BearishCrossover(AlertRule):
    signal_sensitivity: float = 0.1
    max_macd_value: float = 5.0
```

#### Moving Average Alerts
```python
class SMA_BreakoutAlert(AlertRule):
    sma_period: int = 20
    breakout_percentage: float = 0.5  # 0.5% above SMA
    volume_confirmation: bool = True   # Require volume spike
```

### Price Movement Alerts

#### Gap Alerts
```python
class PriceGapAlert(AlertRule):
    gap_threshold: float = 0.02  # 2% gap
    direction: str = "both"      # "up", "down", or "both"
    exclude_first_candle: bool = True  # Exclude market open gaps
```

#### Volume Spike Alerts  
```python
class VolumeSpike(AlertRule):
    volume_multiplier: float = 2.0    # 2x average volume
    lookback_period: int = 20         # 20-period average
    min_absolute_volume: int = 100000 # Minimum volume threshold
```

### Portfolio Alerts

#### Risk Management Alerts
```python
class DrawdownAlert(AlertRule):
    max_drawdown: float = 0.05    # 5% portfolio drawdown
    calculation_period: int = 30  # 30-day rolling
    
class ConcentrationAlert(AlertRule):
    max_single_position: float = 0.25  # 25% of portfolio
    max_sector_exposure: float = 0.40   # 40% in one sector
```

---

## 📊 Monitoring and Analytics

### Key Performance Indicators (KPIs)

#### Cost Metrics
- **API Calls per Day**: Target <200 (vs current 600)
- **Monthly API Cost**: Target <$30 (vs current $125.40) 
- **Cost per Decision**: Target <$0.02 (vs current $0.38)
- **API Efficiency**: Calls per profitable decision

#### Alert Performance Metrics
- **Alert Accuracy**: True positive rate of alerts
- **Response Time**: Time from alert to action
- **False Positive Rate**: Target <5%
- **Alert Coverage**: % of profitable opportunities caught

#### Trading Performance Metrics
- **Decision Quality**: Win rate of alert-triggered trades
- **Portfolio Performance**: Risk-adjusted returns
- **Risk Metrics**: Drawdown, volatility, Sharpe ratio
- **Execution Quality**: Slippage, timing, fills

---

## 🔒 Risk Management

### Alert System Risks

#### False Positives
- **Risk**: Too many unnecessary alerts increase costs
- **Mitigation**: Alert cooldown periods, confidence thresholds
- **Monitoring**: Track false positive rates, optimize thresholds

#### False Negatives  
- **Risk**: Missing important market opportunities
- **Mitigation**: Multiple complementary alert types, sensitivity analysis
- **Monitoring**: Compare with continuous monitoring benchmark

#### System Failures
- **Risk**: Alert system failures could halt trading
- **Mitigation**: Fallback to continuous monitoring, redundant systems
- **Monitoring**: System health checks, alert system SLA tracking

### Risk Controls (proposed knobs — not yet in `config.py`)
```python
# Proposed safety knobs for a continuous alert loop
MAX_ALERTS_PER_HOUR = 20        # Prevent alert spam
MIN_ALERT_INTERVAL = 300        # 5-minute minimum between alerts
ALERT_CONFIDENCE_THRESHOLD = 0.6 # Only high-confidence alerts
SYSTEM_HEALTH_CHECKS = True     # Continuous system monitoring
FALLBACK_MODE_ENABLED = True    # Fallback to continuous monitoring
```

---

## 🎯 Success Criteria

### Must-Have (MVP)
- **80% API Cost Reduction**: Monthly costs under $30
- **Alert Response Time**: <60 seconds from trigger to action
- **System Reliability**: 99%+ uptime for alert system
- **Decision Quality**: Maintained or improved vs continuous monitoring

### Should-Have
- **False Positive Rate**: <5% of total alerts
- **Alert Coverage**: >90% of profitable opportunities detected
- **Historical Backtesting**: Accurate simulation on 6+ months data
- **Cost Tracking**: Real-time cost monitoring and optimization

### Nice-to-Have
- **ML Optimization**: Automated threshold optimization
- **Multi-timeframe Alerts**: Coordinated alerts across timeframes
- **Advanced Analytics**: Comprehensive performance insights
- **External Integrations**: Third-party notification systems

---

## 📊 Current System Status

### What works today
- 4 alert rule types implemented and wired into `apps/trader.py`
- Cooldown management prevents alert spam
- Callback system for extensible alert handling
- Exercised via `apps/health_check.py` (no dedicated alert unit tests yet)

### Available Alert Rules (shipped)
```python
PriceCrossRule        # Price threshold crossovers
RSIExtremeRule        # RSI overbought/oversold detection
VolumeSpikRule        # Volume surge identification
MACDCrossRule         # MACD signal line crossovers
```

### System Integration Status
**✅ Core Integration Complete**
- Configuration system integration
- Logging system integration  
- Test suite integration
- Health check integration

---

## 🎯 Future Enhancement Opportunities

### Potential Extensions
1. **Live Trading Integration**: Connect with trading execution
2. **Advanced Alert Rules**: Support/resistance, pattern recognition
3. **Machine Learning**: Dynamic threshold optimization
4. **Portfolio Alerts**: Risk management and performance alerts
5. **Multi-timeframe**: Coordinated alerts across timeframes

### Scalability
- Current system supports unlimited symbols
- Event-driven architecture ensures efficient resource usage
- Modular design allows easy addition of new alert types

---

**Document type**: design + roadmap (built sections are live; "Proposed" /
"Roadmap" sections are intent, not shipped code).