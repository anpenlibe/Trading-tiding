"""Central configuration for the trading bot.

Loaded from .env (python-dotenv). SYMBOLS come from the stock registry, selected
by TRADING_STRATEGY. Importing this module validates that at least one AI
provider key is set and that the core risk parameters are sane.
"""

import os
import logging
from dotenv import load_dotenv
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Environment Configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
IS_DEVELOPMENT = ENVIRONMENT == "development"

logger.info("Environment: %s", ENVIRONMENT.upper())

# API Keys
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")        # singular; pool is GEMINI_API_KEY_1..N
GROQ_API_KEY        = os.getenv("GROQ_API_KEY")          # singular; pool is GROQ_API_KEY_1..N
ZERODHA_API_KEY     = os.getenv("ZERODHA_API_KEY")
ZERODHA_API_SECRET  = os.getenv("ZERODHA_API_SECRET")
ZERODHA_ACCESS_TOKEN= os.getenv("ZERODHA_ACCESS_TOKEN")  # Generated after login

# Validate critical API keys. At least one AI provider key must be configured.
# Keys may be a single PROVIDER_API_KEY or a numbered pool (PROVIDER_API_KEY_1,
# _2, ...) — the provider coordinator cycles the pool; here we only need to know
# that at least one real (non-placeholder) key exists.
_PLACEHOLDERS = (
    "", "your-claude-api-key-here", "your-gemini-api-key-here",
    "your-groq-api-key-here", "your-zerodha-api-key-here",
)

def _has_provider_key(prefix: str) -> bool:
    names = [f"{prefix}_API_KEY"] + [f"{prefix}_API_KEY_{i}" for i in range(1, 11)]
    for n in names:
        val = (os.getenv(n) or "").strip()
        if val and val not in _PLACEHOLDERS:
            return True
    return False

has_ai_key = any(_has_provider_key(p) for p in ("GEMINI", "GROQ"))
if not has_ai_key:
    raise ValueError(
        "Please set at least one AI API key (GROQ_API_KEY/_1.. or "
        "GEMINI_API_KEY/_1..) in the .env file"
    )

if not ZERODHA_API_KEY or ZERODHA_API_KEY == "your-zerodha-api-key-here":
    logger.warning("ZERODHA_API_KEY not configured - live/paper collection will fail (backtests still work)")

# Log configured market-data APIs (Zerodha is the only source).
configured_apis = []
if ZERODHA_API_KEY and ZERODHA_API_KEY != "your-zerodha-api-key-here":
    configured_apis.append("Zerodha")

logger.info("Configured market-data APIs: %s", ', '.join(configured_apis) if configured_apis else 'None (Zerodha not configured)')

# Trading Parameters — ₹50,000 capital (≈5 positions × ₹10k).
# Strategy knobs live here in code, NOT in .env (.env is for secrets only).
INITIAL_CAPITAL     = 50000.0
MAX_RISK_PER_TRADE  = 0.015
MAX_DAILY_LOSS      = 0.05
MAX_DRAWDOWN        = 0.15

# Position Sizing
MIN_TRADE_VALUE     = 3000.0  # floor: keeps flat DP-charge drag under ~0.6%/round-trip
MAX_POSITION_SIZE   = float(os.getenv("MAX_POSITION_SIZE", "0.20"))  # max fraction of capital per position

# UPDATED: Centralized Symbol Management
# Import stock registry for intelligent symbol selection
try:
    from src.platform.registry import (
        get_swing_trading_symbols, 
        get_conservative_symbols,
        get_diversified_symbols,
        get_symbols_by_sector
    )
    
    # Strategy-based symbol selection (code constant, not env-driven)
    TRADING_STRATEGY = "diversified"
    
    if TRADING_STRATEGY == "conservative":
        SYMBOLS = get_conservative_symbols(max_symbols=8)
    elif TRADING_STRATEGY == "diversified":
        SYMBOLS = get_diversified_symbols(max_symbols=20)
    elif TRADING_STRATEGY == "swing":
        SYMBOLS = get_swing_trading_symbols(max_symbols=8)
    elif TRADING_STRATEGY == "tech_focus":
        SYMBOLS = get_symbols_by_sector("technology")[:6] + get_symbols_by_sector("banking")[:4]
    else:
        # Default: use swing trading symbols
        SYMBOLS = get_swing_trading_symbols(max_symbols=8)

    logger.info("%s strategy: %d symbols (%s)", TRADING_STRATEGY, len(SYMBOLS), ', '.join(SYMBOLS))

    # Add Nifty 50 for market-wide regime detection (if not already present)
    if "^NSEI" not in SYMBOLS:
        SYMBOLS.append("^NSEI")
        logger.info("Added Nifty 50 (^NSEI) for market regime analysis")

except ImportError:
    # Fallback to hardcoded symbols if stock registry not available
    logger.warning("Stock registry not available, using fallback symbols")
    SYMBOLS = [
        "RELIANCE", "TCS", "INFY", "ICICIBANK", "SBIN",
        "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HDFCBANK",
        "^NSEI"  # Nifty 50 for market regime
    ]

# Market Hours (IST)
MARKET_TIMEZONE = pytz.timezone('Asia/Kolkata')
MARKET_OPEN     = "09:15"
MARKET_CLOSE    = "15:30"
PRE_MARKET_OPEN = "09:00"
POST_MARKET_CLOSE = "15:45"

# Data Source Configuration
# Zerodha is the sole market-data source (no Yahoo/Mock fallback). Live/paper
# collection requires a Zerodha session; backtests read the local SQLite DB.

# Logging
LOG_LEVEL      = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT     = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT= "%Y-%m-%d %H:%M:%S"

# Paths
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_PATH, "data")
LOGS_PATH = os.path.join(DATA_PATH, "logs")

# Optional raw data folders
HISTORICAL_DATA_PATH = os.path.join(DATA_PATH, "historical")
LIVE_DATA_PATH       = os.path.join(DATA_PATH, "live")

# Database path. A single SQLite DB holds all market data (historical + runtime).
# It is generated locally via apps/data_collector.py from Zerodha and is
# gitignored — not committed — so each user populates their own with their token.
REPO_ROOT         = os.path.dirname(BASE_PATH)
RUNTIME_DATA_PATH = os.path.join(REPO_ROOT, "data")
DB_PATH           = os.path.join(RUNTIME_DATA_PATH, "market_data.sqlite")

# ============= AI PROVIDER SETTINGS =============
# The AI provider fallback chain lives in src/ai/provider_coordinator.py, which
# owns its config via env: it reads ENABLED_AI_PROVIDERS (default "groq,gemini")
# and the numbered key pools (GROQ_API_KEY_1..N, GEMINI_API_KEY_1..N) directly.
# The Groq and Gemini models are FIXED in the coordinator's chain — there are no
# GROQ_MODEL / GEMINI_MODEL knobs. Claude was removed as a provider.

# Risk Management
STOP_LOSS_PERCENT     = float(os.getenv("STOP_LOSS_PERCENT", "0.015"))
TAKE_PROFIT_PERCENT   = float(os.getenv("TAKE_PROFIT_PERCENT", "0.03"))

# Emergency Threshold Defaults (for AI monitoring system)
EMERGENCY_STOP_LOSS_PCT = float(os.getenv('EMERGENCY_STOP_LOSS_PCT', '-3.5'))  # Default -3.5%
EMERGENCY_TAKE_PROFIT_PCT = float(os.getenv('EMERGENCY_TAKE_PROFIT_PCT', '4.0'))  # Default +4.0%
EMERGENCY_RECHECK_PCT = float(os.getenv('EMERGENCY_RECHECK_PCT', '2.0'))  # Default ±2.0%

# Proactive throttle: minimum wall-clock seconds between AI calls to the SAME
# provider, derived from the free-tier TOKENS-PER-MINUTE ceiling (not a guess).
# Groq gpt-oss-120b = 8K TPM/key; backtest pools 3 keys = 24K TPM. A call is ~3K
# tokens (≈2K prompt + ~1K completion), so ~8 calls/min stays under budget →
# ~7.5s spacing; round to 10s for headroom. Rotation spreads load across the keys;
# this keeps the aggregate token RATE below the ceiling so the good models stay warm
# instead of all cooling and dumping everything onto the weak 20b fallback.
AI_CALL_MIN_INTERVAL_SEC = float(os.getenv('AI_CALL_MIN_INTERVAL_SEC', '10.0'))
# A 429'd (model,key) is benched this long. A TPM bucket refills over a full minute,
# so 60s lets it actually recover — a shorter bench just retries into the same wall.
RATE_LIMIT_COOLDOWN_SEC = int(os.getenv('RATE_LIMIT_COOLDOWN_SEC', '60'))

# Paper Trading Settings
# PAPER_TRADE_COMMISSION is a legacy flat per-trade fee, superseded by the
# turnover-based Indian-equity charge model in src/core/transaction_costs.py.
# Kept (default 0.0) as an optional extra fixed fee on top of computed charges.
PAPER_TRADE_COMMISSION = float(os.getenv("PAPER_TRADE_COMMISSION", "0.0"))
PAPER_TRADE_SLIPPAGE   = float(os.getenv("PAPER_TRADE_SLIPPAGE", "0.0005"))
# TRADING_PRODUCT selects the charge schedule: 'delivery' (CNC, multi-day swing)
# or 'intraday' (MIS, same-day). The AI does multi-day swing trades → delivery.
TRADING_PRODUCT = os.getenv("TRADING_PRODUCT", "delivery").lower()

# Performance Tracking
MIN_TRADES_FOR_ANALYSIS   = 15
PERFORMANCE_REPORT_INTERVAL = "daily"

# ============= DATA VALIDATION CONFIGURATION =============
# Data quality thresholds
VALIDATION_MAX_PRICE_CHANGE = float(os.getenv('VALIDATION_MAX_PRICE_CHANGE', '0.20'))  # 20% circuit breaker
VALIDATION_MIN_VOLUME = int(os.getenv('VALIDATION_MIN_VOLUME', '100'))

# ============= CACHE CONFIGURATION =============
# Performance optimization
CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '300'))  # 5 minutes

# ============= TECHNICAL INDICATOR CONFIGURATION =============
# Moving averages
SMA_PERIODS = [20, 50, 200]  # Short, medium, long term
VOLUME_SMA_PERIOD = int(os.getenv('VOLUME_SMA_PERIOD', '20'))

# RSI settings
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
RSI_OVERBOUGHT = float(os.getenv('RSI_OVERBOUGHT', '70'))
RSI_OVERSOLD = float(os.getenv('RSI_OVERSOLD', '30'))

# MACD settings  
MACD_FAST = int(os.getenv('MACD_FAST', '12'))
MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))

# ============= DATA COLLECTION CONFIGURATION =============
# Data retrieval settings
# Default candle interval the decision pipeline reads from the DB. The collector
# stores multiple intervals side by side (e.g. '1m' intraday, '1d' daily); swing
# decisions read daily. Readers filter price_data by this unless overridden.
DEFAULT_DATA_INTERVAL = os.getenv('DATA_INTERVAL', '1d')
DEFAULT_PERIODS = int(os.getenv('DEFAULT_PERIODS', '200'))
MIN_DATA_FOR_INDICATORS = int(os.getenv('MIN_DATA_FOR_INDICATORS', '20'))
RECENT_DATA_LOOKBACK = int(os.getenv('RECENT_DATA_LOOKBACK', '20'))

# ============= AI BRAIN CONFIGURATION =============
# Decision making settings
MAX_DECISION_HISTORY = int(os.getenv('MAX_DECISION_HISTORY', '100'))

# ============= PERFORMANCE CONFIGURATION =============
# Analysis settings
DEFAULT_TRADE_HISTORY_LIMIT = int(os.getenv('DEFAULT_TRADE_HISTORY_LIMIT', '50'))

# ============= LIQUIDITY CONFIGURATION =============
# Stock filtering settings - MIN_LIQUIDITY_VOLUME moved to stock_registry.py to avoid circular import

# ============= ALERT CONFIGURATION =============
# Alert system settings
ENABLE_ALERTS = True
PRICE_ALERT_THRESHOLD = float(os.getenv("PRICE_ALERT_THRESHOLD", "0.02"))  # 2% move
VOLUME_SPIKE_MULTIPLIER = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))  # default spike threshold for VolumeSpikRule
RSI_ALERT_DURATION = 2  # Periods RSI must stay extreme
# Wake the AI when price has travelled this fraction of the way from entry toward
# its stop/target — anchored to the entry→level DISTANCE, not a flat % of the level
# (a flat % overshoots past entry on tight ATR stops and fires at entry). 0.8 = wake
# at 80% of the way to the level, before the executor's mechanical auto-close.
ALERT_APPROACH_FRACTION = float(os.getenv("ALERT_APPROACH_FRACTION", "0.8"))
# Minimum |macd - signal|, as a % of price, for a MACD cross to count. On 1-minute
# data the lines hug zero and flip on noise (we saw sells fire at gaps of 0.006);
# requiring real separation filters the whipsaw. Price-relative so it scales across
# a ₹250 and a ₹3000 stock.
MACD_CROSS_MIN_GAP_PCT = float(os.getenv("MACD_CROSS_MIN_GAP_PCT", "0.03"))
# MACD-cross cooldown (minutes) — longer than the old 45 so a chopping stock can't
# re-wake the special pass every few minutes.
MACD_CROSS_COOLDOWN_MIN = int(os.getenv("MACD_CROSS_COOLDOWN_MIN", "90"))

# Development/Debug Settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DRY_RUN    = os.getenv("DRY_RUN", "true").lower() == "true"

# NEW: Symbol Management Functions
def get_trading_symbols(strategy: str = None) -> list:
    """
    Get symbols for specific trading strategy.
    
    Args:
        strategy: "conservative", "swing", "diversified", "tech_focus", or None for current
    
    Returns:
        List of trading symbols
    """
    try:
        from src.platform.registry import (
            get_swing_trading_symbols, 
            get_conservative_symbols,
            get_diversified_symbols,
            get_symbols_by_sector
        )
        
        if strategy == "conservative":
            return get_conservative_symbols(max_symbols=8)
        elif strategy == "diversified":
            return get_diversified_symbols(max_symbols=10)
        elif strategy == "swing":
            return get_swing_trading_symbols(max_symbols=8)
        elif strategy == "tech_focus":
            return get_symbols_by_sector("technology")[:6] + get_symbols_by_sector("banking")[:4]
        else:
            return SYMBOLS  # Current configured symbols
    except ImportError:
        return SYMBOLS  # Fallback


def switch_trading_strategy(new_strategy: str):
    """
    Switch to a different trading strategy.
    
    Args:
        new_strategy: "conservative", "swing", "diversified", "tech_focus"
    """
    global SYMBOLS
    new_symbols = get_trading_symbols(new_strategy)
    SYMBOLS = new_symbols
    logger.info("Switched to %s strategy: %d symbols (%s)", new_strategy, len(SYMBOLS), ', '.join(SYMBOLS))


def get_symbol_info(symbol: str) -> dict:
    """
    Get detailed information about a trading symbol.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Dict with symbol information or empty dict if not found
    """
    try:
        from src.platform.registry import get_stock_registry
        registry = get_stock_registry()
        info = registry.get_stock_info(symbol)
        if info:
            return {
                'symbol': info.symbol,
                'company_name': info.company_name,
                'sector': info.sector.value,
                'market_cap': info.market_cap.value,
                'liquidity': info.liquidity.value,
                'is_index_stock': info.is_index_stock,
                'avg_daily_volume': info.avg_daily_volume,
                'typical_spread_bps': info.typical_spread_bps,
                'notes': info.notes
            }
    except ImportError:
        pass
    
    return {}


# Validate configuration
def validate_config():
    errors = []
    if INITIAL_CAPITAL <= 0:
        errors.append("INITIAL_CAPITAL must be positive")
    if not 0 < MAX_RISK_PER_TRADE <= 0.05:
        errors.append("MAX_RISK_PER_TRADE should be between 0 and 5%")
    if not SYMBOLS:
        errors.append("No symbols configured for trading")
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

validate_config()

# Helper functions
def is_market_hours(timestamp=None):
    if timestamp is None:
        timestamp = datetime.now(MARKET_TIMEZONE)
    elif timestamp.tzinfo is None:
        timestamp = MARKET_TIMEZONE.localize(timestamp)
    current_time = timestamp.time()
    market_open = datetime.strptime(MARKET_OPEN, "%H:%M").time()
    market_close = datetime.strptime(MARKET_CLOSE, "%H:%M").time()
    if timestamp.weekday() > 4:
        return False
    return market_open <= current_time <= market_close

def calculate_position_size(capital: float, risk_percent: float, entry_price: float, stop_loss: float) -> int:
    risk_amount   = capital * risk_percent
    risk_per_share= abs(entry_price - stop_loss)
    if risk_per_share <= 0:
        return 0
    position_size = int(risk_amount / risk_per_share)
    min_shares    = int(MIN_TRADE_VALUE / entry_price) + 1
    max_shares    = int((capital * MAX_POSITION_SIZE) / entry_price)
    return min(max(position_size, min_shares), max_shares)


# Print configuration summary
# Test mode detection
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

if TEST_MODE:
    logger.warning("TEST MODE ACTIVE - Using relaxed trading limits")

    # Override production limits for testing
    MIN_TRADE_VALUE = 100.0  # ₹100 instead of ₹500
    MAX_POSITION_SIZE = 0.50  # 50% instead of 20%
    MAX_RISK_PER_TRADE = 0.05  # 5% instead of 1.5%

    # More relaxed trading parameters
    MIN_CONFIDENCE_THRESHOLD = 0.3  # Lower threshold for testing

    # Use shorter intervals for faster testing
    TRADING_CYCLE_SECONDS = 60  # 1 minute instead of 5

    logger.warning(
        "Test mode overrides applied: min_trade_value=%s, max_position_size=%s%%, max_risk_per_trade=%s%%",
        MIN_TRADE_VALUE, MAX_POSITION_SIZE * 100, MAX_RISK_PER_TRADE * 100,
    )

# ============= TRADING MODE =============
# paper (default) | live | backtest. Mode-specific safety lives in
# src/core/trading_modes.py. There is no mock data source to guard against —
# Zerodha is the only source, so live mode simply requires a Zerodha session.
TRADING_MODE = os.getenv('TRADING_MODE', 'paper')

logger.info("Market-data source: Zerodha only | Trading mode: %s", TRADING_MODE)
