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
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")        # For Gemini auditor
GROQ_API_KEY        = os.getenv("GROQ_API_KEY")          # For Groq ultra-fast inference
ZERODHA_API_KEY     = os.getenv("ZERODHA_API_KEY")
ZERODHA_API_SECRET  = os.getenv("ZERODHA_API_SECRET")
ZERODHA_ACCESS_TOKEN= os.getenv("ZERODHA_ACCESS_TOKEN")  # Generated after login

# Validate critical API keys
# Note: At least one AI provider API key must be configured
# AI system uses multi-provider fallback: Groq → Gemini → Claude
has_ai_key = any([
    ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-claude-api-key-here",
    GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here",
    GROQ_API_KEY and GROQ_API_KEY != "your-groq-api-key-here"
])
if not has_ai_key:
    raise ValueError("Please set at least one AI API key (ANTHROPIC_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY) in .env file")

if not ZERODHA_API_KEY or ZERODHA_API_KEY == "your-zerodha-api-key-here":
    logger.warning("ZERODHA_API_KEY not configured - using mock data")

# Log configured APIs
configured_apis = []
if ZERODHA_API_KEY and ZERODHA_API_KEY != "your-zerodha-api-key-here":
    configured_apis.append("Zerodha")

logger.info("Configured APIs: %s", ', '.join(configured_apis) if configured_apis else 'None (using mock data)')

# Trading Parameters - UPDATED FOR ₹10,000 CAPITAL
INITIAL_CAPITAL     = float(os.getenv("INITIAL_CAPITAL", "10000.0"))
MAX_RISK_PER_TRADE  = float(os.getenv("MAX_RISK_PER_TRADE", "0.015"))
MAX_DAILY_LOSS      = float(os.getenv("MAX_DAILY_LOSS", "0.05"))
MAX_DRAWDOWN        = float(os.getenv("MAX_DRAWDOWN", "0.15"))

# Position Sizing
MIN_TRADE_VALUE     = 500.0
MAX_POSITION_SIZE   = float(os.getenv("MAX_POSITION_SIZE", "0.20"))  # max fraction of capital per position

# UPDATED: Centralized Symbol Management
# Import stock registry for intelligent symbol selection
try:
    from src.data.stock_registry import (
        get_swing_trading_symbols, 
        get_conservative_symbols,
        get_diversified_symbols,
        get_symbols_by_sector
    )
    
    # Strategy-based symbol selection
    TRADING_STRATEGY = os.getenv("TRADING_STRATEGY", "swing").lower()
    
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
# Source selection/priority is handled by DataCollector._init_apis
# (Zerodha → Yahoo → Mock); there is no single DATA_SOURCE switch.
USE_MOCK_DATA= os.getenv("USE_MOCK_DATA", "false").lower() == "true"

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

# Database paths.
# BUNDLED_DB_PATH is the read-only historical snapshot committed in the repo and
# read by the backtester. Runtime collection (live/mock) writes to a SEPARATE DB
# under the gitignored repo-root data/ dir, so running the trader never mutates
# the committed snapshot. The runtime DB is seeded from the snapshot on first use
# (see DatabaseManager) so the trader still has historical context.
BUNDLED_DB_PATH   = os.path.join(DATA_PATH, "market_data.sqlite")          # src/data/ (committed)
REPO_ROOT         = os.path.dirname(BASE_PATH)
RUNTIME_DATA_PATH = os.path.join(REPO_ROOT, "data")
DB_PATH           = os.path.join(RUNTIME_DATA_PATH, "market_data.sqlite")  # data/ (gitignored, runtime)

# ============= AI API SETTINGS =============
# Multi-Provider Fallback Architecture (2025-10-03 Refactor):
# - ProviderCoordinator handles automatic fallback between providers
# - Default chain: Groq llama-3.3 → Groq llama-3.1 → Gemini Pro → Claude → rule-based
# - Per-model rate limiting allows multi-model Groq usage (separate rate pools)
# - AI_PROVIDER setting is deprecated but kept for backward compatibility
AI_PROVIDER        = os.getenv("AI_PROVIDER", "groq")  # Deprecated: Coordinator now manages providers

# Claude API Settings
CLAUDE_MODEL       = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
CLAUDE_MAX_TOKENS  = int(os.getenv("CLAUDE_MAX_TOKENS", "1000"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.3"))

# Gemini API Settings
GEMINI_MODEL       = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # Fast for pipeline testing
GEMINI_MAX_TOKENS  = int(os.getenv("GEMINI_MAX_TOKENS", "4000"))
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.6"))
# Note: Coordinator uses gemini-2.5-pro in fallback chain (better quality, 2 RPM limit)

# Groq API Settings (Multi-Model Support)
GROQ_MODEL         = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")  # Primary model
GROQ_MAX_TOKENS    = int(os.getenv("GROQ_MAX_TOKENS", "8000"))
GROQ_TEMPERATURE   = float(os.getenv("GROQ_TEMPERATURE", "0.6"))
# Available models: llama-3.3-70b-versatile, llama-3.1-70b-versatile, mixtral-8x7b-32768
# Note: Coordinator uses both llama-3.3 and llama-3.1 with separate rate limit pools

# Risk Management
STOP_LOSS_PERCENT     = float(os.getenv("STOP_LOSS_PERCENT", "0.015"))
TAKE_PROFIT_PERCENT   = float(os.getenv("TAKE_PROFIT_PERCENT", "0.03"))
TRAILING_STOP_PERCENT = 0.01  # NOTE: defined but currently unread anywhere

# Emergency Threshold Defaults (for AI monitoring system)
EMERGENCY_STOP_LOSS_PCT = float(os.getenv('EMERGENCY_STOP_LOSS_PCT', '-3.5'))  # Default -3.5%
EMERGENCY_TAKE_PROFIT_PCT = float(os.getenv('EMERGENCY_TAKE_PROFIT_PCT', '4.0'))  # Default +4.0%
EMERGENCY_RECHECK_PCT = float(os.getenv('EMERGENCY_RECHECK_PCT', '2.0'))  # Default ±2.0%

# Paper Trading Settings
PAPER_TRADE_COMMISSION = float(os.getenv("PAPER_TRADE_COMMISSION", "0.0"))
PAPER_TRADE_SLIPPAGE   = float(os.getenv("PAPER_TRADE_SLIPPAGE", "0.0005"))

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
DEFAULT_PERIODS = int(os.getenv('DEFAULT_PERIODS', '200'))
MIN_DATA_FOR_INDICATORS = int(os.getenv('MIN_DATA_FOR_INDICATORS', '20'))
RECENT_DATA_LOOKBACK = int(os.getenv('RECENT_DATA_LOOKBACK', '20'))

# ============= AI BRAIN CONFIGURATION =============
# Decision making settings
MAX_DECISION_HISTORY = int(os.getenv('MAX_DECISION_HISTORY', '100'))

# ============= SIMULATION CONFIGURATION =============
# Backtesting and simulation settings
SIMULATION_PERIODS = int(os.getenv('SIMULATION_PERIODS', '50'))
SIMULATION_BASE_PRICE = float(os.getenv('SIMULATION_BASE_PRICE', '2850'))

# ============= DATA SOURCE CONFIGURATION =============
# Mock data generation
MOCK_VOLUME_RANGE_MIN = int(os.getenv('MOCK_VOLUME_RANGE_MIN', '100000'))
MOCK_VOLUME_RANGE_MAX = int(os.getenv('MOCK_VOLUME_RANGE_MAX', '1000000'))

# ============= PERFORMANCE CONFIGURATION =============
# Analysis settings
DEFAULT_TRADE_HISTORY_LIMIT = int(os.getenv('DEFAULT_TRADE_HISTORY_LIMIT', '50'))

# ============= LIQUIDITY CONFIGURATION =============
# Stock filtering settings - MIN_LIQUIDITY_VOLUME moved to stock_registry.py to avoid circular import

# ============= ALERT CONFIGURATION =============
# Alert system settings
ENABLE_ALERTS = True
ALERT_COOLDOWN_MINUTES = 30           # NOTE: defined but currently unread anywhere
PRICE_ALERT_THRESHOLD = float(os.getenv("PRICE_ALERT_THRESHOLD", "0.02"))  # 2% move
VOLUME_SPIKE_MULTIPLIER = 2.0         # NOTE: trader.py hardcodes 2.0 instead of reading this
RSI_ALERT_DURATION = 2  # Periods RSI must stay extreme

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
        from src.data.stock_registry import (
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
        from src.data.stock_registry import get_stock_registry
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
    ALERT_COOLDOWN_MINUTES = 5  # 5 minutes instead of 30

    logger.warning(
        "Test mode overrides applied: min_trade_value=%s, max_position_size=%s%%, max_risk_per_trade=%s%%",
        MIN_TRADE_VALUE, MAX_POSITION_SIZE * 100, MAX_RISK_PER_TRADE * 100,
    )

# ============= DATA SOURCE SAFETY CONFIGURATION =============

# Mock API Safety - CRITICAL for production
ALLOW_MOCK_DATA_IN_LIVE_TRADING = False  # NEVER change this to True in production

# Trading mode validation
REQUIRE_REAL_DATA_FOR_LIVE_TRADING = True
TRADING_MODE = os.getenv('TRADING_MODE', 'paper')  # Default to paper trading

if TRADING_MODE == 'live' and not REQUIRE_REAL_DATA_FOR_LIVE_TRADING:
    logger.warning("Live trading without real data validation - review configuration!")

logger.info("Data source priority: Zerodha (1) > Yahoo Finance (2) > Mock (testing only)")
logger.info(
    "Mock data in live trading: %s",
    "DISABLED" if not ALLOW_MOCK_DATA_IN_LIVE_TRADING else "ENABLED",
)
