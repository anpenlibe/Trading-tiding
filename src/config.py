"""
Module: config.py
Purpose: Configuration settings for the trading bot
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-30 - UPDATED: Now uses centralized stock registry

CHANGES:
- SYMBOLS now imported from stock_registry.py
- Added trading strategy symbol selection
- Improved symbol management with sector awareness
"""

import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

# API Keys - ONLY ZERODHA NOW
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
ZERODHA_API_KEY     = os.getenv("ZERODHA_API_KEY")
ZERODHA_API_SECRET  = os.getenv("ZERODHA_API_SECRET")
ZERODHA_ACCESS_TOKEN= os.getenv("ZERODHA_ACCESS_TOKEN")  # Generated after login

# Validate critical API keys
if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-claude-api-key-here":
    raise ValueError("Please set ANTHROPIC_API_KEY in .env file")

if not ZERODHA_API_KEY or ZERODHA_API_KEY == "your-zerodha-api-key-here":
    print("⚠️  ZERODHA_API_KEY not configured - using mock data")

# Log configured APIs
configured_apis = []
if ZERODHA_API_KEY and ZERODHA_API_KEY != "your-zerodha-api-key-here":
    configured_apis.append("Zerodha")

print(f"Configured APIs: {', '.join(configured_apis) if configured_apis else 'None (using mock data)'}")

# Trading Parameters - UPDATED FOR ₹10,000 CAPITAL
INITIAL_CAPITAL     = float(os.getenv("INITIAL_CAPITAL", "10000.0"))
MAX_RISK_PER_TRADE  = float(os.getenv("MAX_RISK_PER_TRADE", "0.015"))
MAX_DAILY_LOSS      = float(os.getenv("MAX_DAILY_LOSS", "0.05"))
MAX_DRAWDOWN        = float(os.getenv("MAX_DRAWDOWN", "0.15"))

# Position Sizing
MIN_TRADE_VALUE     = 500.0
MAX_POSITION_SIZE = 0.20
MAX_POSITION_SIZE_PERCENT   = 0.20

# UPDATED: Centralized Symbol Management
# Import stock registry for intelligent symbol selection
try:
    from src.stock_registry import (
        get_swing_trading_symbols, 
        get_conservative_symbols,
        get_diversified_symbols,
        get_symbols_by_sector
    )
    
    # Strategy-based symbol selection
    TRADING_STRATEGY = os.getenv("TRADING_STRATEGY", "swing").lower()
    
    if TRADING_STRATEGY == "conservative":
        SYMBOLS = get_conservative_symbols(max_symbols=8)
        print(f"📊 Conservative strategy: {len(SYMBOLS)} symbols")
    elif TRADING_STRATEGY == "diversified":
        SYMBOLS = get_diversified_symbols(max_symbols=10)
        print(f"🌐 Diversified strategy: {len(SYMBOLS)} symbols")
    elif TRADING_STRATEGY == "swing":
        SYMBOLS = get_swing_trading_symbols(max_symbols=8)
        print(f"⚡ Swing trading strategy: {len(SYMBOLS)} symbols")
    elif TRADING_STRATEGY == "tech_focus":
        SYMBOLS = get_symbols_by_sector("technology")[:6] + get_symbols_by_sector("banking")[:4]
        print(f"💻 Tech-focused strategy: {len(SYMBOLS)} symbols")
    else:
        # Default: use swing trading symbols
        SYMBOLS = get_swing_trading_symbols(max_symbols=8)
        print(f"🔄 Default swing strategy: {len(SYMBOLS)} symbols")
    
    print(f"Selected symbols: {', '.join(SYMBOLS)}")
    
except ImportError:
    # Fallback to hardcoded symbols if stock registry not available
    print("⚠️  Stock registry not available, using fallback symbols")
    SYMBOLS = [
        "RELIANCE", "TCS", "INFY", "ICICIBANK", "SBIN",
        "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HDFCBANK"
    ]

# Market Hours (IST)
MARKET_TIMEZONE = pytz.timezone('Asia/Kolkata')
MARKET_OPEN     = "09:15"
MARKET_CLOSE    = "15:30"
PRE_MARKET_OPEN = "09:00"
POST_MARKET_CLOSE = "15:45"

# Data Source Configuration
DATA_SOURCE  = "zerodha"
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

# Database - UNIFIED PATH FOR HISTORICAL AND LIVE
DB_PATH = os.path.join(DATA_PATH, "market_data.sqlite")

# Claude API Settings
CLAUDE_MODEL       = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
CLAUDE_MAX_TOKENS  = int(os.getenv("CLAUDE_MAX_TOKENS", "1000"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.3"))

# Strategy Settings
STRATEGIES = {
    "mean_reversion": {
        "enabled": True,
        "lookback_period": 20,
        "entry_threshold": 0.015,
        "exit_threshold": 0.01,
        "min_volume_ratio": 0.8
    }
}

# Risk Management
STOP_LOSS_PERCENT     = 0.015
TAKE_PROFIT_PERCENT   = 0.03
TRAILING_STOP_PERCENT = 0.01

# Paper Trading Settings
PAPER_TRADE_COMMISSION = 0.0
PAPER_TRADE_SLIPPAGE   = 0.0005

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
ALERT_COOLDOWN_MINUTES = 30
PRICE_ALERT_THRESHOLD = 0.02  # 2% move
VOLUME_SPIKE_MULTIPLIER = 2.0
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
        from src.stock_registry import (
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
    print(f"🔄 Switched to {new_strategy} strategy: {len(SYMBOLS)} symbols")
    print(f"New symbols: {', '.join(SYMBOLS)}")


def get_symbol_info(symbol: str) -> dict:
    """
    Get detailed information about a trading symbol.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Dict with symbol information or empty dict if not found
    """
    try:
        from src.stock_registry import get_stock_registry
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
if __name__ == "__main__":
    print("\n🤖 Trading Bot Configuration Summary")
    print("=" * 50)
    print(f"💰 Capital: ₹{INITIAL_CAPITAL:,.0f}")
    print(f"📊 Strategy: {TRADING_STRATEGY.title()}")
    print(f"📈 Symbols: {len(SYMBOLS)} - {', '.join(SYMBOLS[:5])}{'...' if len(SYMBOLS) > 5 else ''}")
    print(f"⚠️  Risk per trade: {MAX_RISK_PER_TRADE*100:.1f}%")
    print(f"🛑 Stop loss: {STOP_LOSS_PERCENT*100:.1f}%")
    print(f"🎯 Target profit: {TAKE_PROFIT_PERCENT*100:.1f}%")
    print(f"🧠 Claude model: {CLAUDE_MODEL}")
    print(f"🏪 Market hours: {MARKET_OPEN} - {MARKET_CLOSE} IST")
    print("=" * 50)

# Testing Configuration
MIN_TRADE_VALUE_TEST = 100  # Minimum trade value for testing
TEST_MODE = False  # Flag to enable test mode
