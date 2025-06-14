"""
Module: config.py
Purpose: Configuration settings for the trading bot
Author: Trading Bot Developer
Created: 2025-06-12
Modified: 2025-06-12
"""

import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ZERODHA_API_KEY = os.getenv("ZERODHA_API_KEY")  # For future use
ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET")  # For future use

# Validate critical API keys
if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-claude-api-key-here":
    raise ValueError("Please set ANTHROPIC_API_KEY in .env file")

# Trading Parameters
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "1000.0"))
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "0.02"))  # 2%
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.06"))  # 6%
MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", "0.20"))  # 20%

# Position Sizing
MIN_TRADE_VALUE = 100.0  # Minimum ₹100 per trade
MAX_POSITION_SIZE = 0.25  # Max 25% of capital in one position

# Symbols to Trade
SYMBOLS = [
    "RELIANCE",  # Reliance Industries
    "TCS",       # Tata Consultancy Services
    "INFY",      # Infosys
    "HDFC",      # HDFC Bank
    "ICICIBANK", # ICICI Bank
    "SBIN",      # State Bank of India
    "BHARTIARTL",# Bharti Airtel
    "ITC",       # ITC Limited
    "KOTAKBANK", # Kotak Mahindra Bank
    "LT"         # Larsen & Toubro
]

# Alternative symbol formats for Yahoo Finance
YAHOO_SYMBOLS = {
    "RELIANCE": ["RELIANCE.NS", "RELIANCE.BO"],
    "TCS": ["TCS.NS", "TCS.BO"],
    "INFY": ["INFY.NS", "INFY.BO"],
    "HDFC": ["HDFC.NS", "HDFC.BO"],
    "ICICIBANK": ["ICICIBANK.NS", "ICICIBANK.BO"],
    "SBIN": ["SBIN.NS", "SBIN.BO"],
    "BHARTIARTL": ["BHARTIARTL.NS", "BHARTIARTL.BO"],
    "ITC": ["ITC.NS", "ITC.BO"],
    "KOTAKBANK": ["KOTAKBANK.NS", "KOTAKBANK.BO"],
    "LT": ["LT.NS", "LT.BO"]
}

# Market Hours (IST)
MARKET_TIMEZONE = pytz.timezone('Asia/Kolkata')
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
PRE_MARKET_OPEN = "09:00"
POST_MARKET_CLOSE = "15:45"

# Data Source Configuration
DATA_SOURCE = os.getenv("DATA_SOURCE", "yahoo")  # yahoo, mock, zerodha
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "false").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Paths
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_PATH, "data")
LOGS_PATH = os.path.join(DATA_PATH, "logs")
HISTORICAL_DATA_PATH = os.path.join(DATA_PATH, "historical")
LIVE_DATA_PATH = os.path.join(DATA_PATH, "live")

# Database
DB_PATH = os.path.join(DATA_PATH, "market_data.db")

# Claude API Settings
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-sonnet-20240229")  # Using Sonnet for cost efficiency
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "1000"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.3"))  # Lower for more consistent trading decisions

# Strategy Settings
STRATEGIES = {
    "mean_reversion": {
        "enabled": True,
        "lookback_period": 20,
        "entry_threshold": 0.02,  # 2% below mean
        "exit_threshold": 0.01,   # 1% above mean
        "min_volume_ratio": 0.8   # Volume must be 80% of average
    },
    "momentum": {
        "enabled": False,  # Start with one strategy
        "lookback_period": 10,
        "breakout_threshold": 0.03,
        "volume_surge": 1.5  # 150% of average volume
    }
}

# Risk Management
STOP_LOSS_PERCENT = 0.02  # 2% stop loss
TAKE_PROFIT_PERCENT = 0.04  # 4% take profit (2:1 risk-reward)
TRAILING_STOP_PERCENT = 0.015  # 1.5% trailing stop

# Paper Trading Settings
PAPER_TRADE_COMMISSION = 20.0  # ₹20 per trade
PAPER_TRADE_SLIPPAGE = 0.001  # 0.1% slippage

# Performance Tracking
MIN_TRADES_FOR_ANALYSIS = 10
PERFORMANCE_REPORT_INTERVAL = "daily"  # daily, weekly

# Alert Settings
ENABLE_ALERTS = True
ALERT_CHANNELS = ["console", "file"]  # Future: email, telegram

# Development/Debug Settings
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"  # Safety first!

# Validate configuration
def validate_config():
    """Validate configuration settings."""
    errors = []
    
    if INITIAL_CAPITAL <= 0:
        errors.append("INITIAL_CAPITAL must be positive")
        
    if not 0 < MAX_RISK_PER_TRADE <= 0.1:
        errors.append("MAX_RISK_PER_TRADE should be between 0 and 10%")
        
    if not SYMBOLS:
        errors.append("No symbols configured for trading")
        
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

# Run validation on import
validate_config()

# Helper functions
def is_market_hours(timestamp=None):
    """Check if given timestamp is during market hours."""
    if timestamp is None:
        timestamp = datetime.now(MARKET_TIMEZONE)
    elif timestamp.tzinfo is None:
        timestamp = MARKET_TIMEZONE.localize(timestamp)
    
    current_time = timestamp.time()
    market_open = datetime.strptime(MARKET_OPEN, "%H:%M").time()
    market_close = datetime.strptime(MARKET_CLOSE, "%H:%M").time()
    
    # Check if it's a weekday (Monday = 0, Sunday = 6)
    if timestamp.weekday() > 4:  # Saturday or Sunday
        return False
    
    return market_open <= current_time <= market_close

def get_symbol_for_yahoo(symbol):
    """Get the appropriate Yahoo Finance symbol format."""
    if symbol in YAHOO_SYMBOLS:
        return YAHOO_SYMBOLS[symbol][0]  # Return primary format
    return f"{symbol}.NS"  # Default to NSE format

# Display configuration on import (if debug)
if DEBUG_MODE:
    print("Configuration loaded:")
    print(f"  Capital: ₹{INITIAL_CAPITAL}")
    print(f"  Risk per trade: {MAX_RISK_PER_TRADE*100}%")
    print(f"  Symbols: {len(SYMBOLS)}")
    print(f"  Data source: {DATA_SOURCE}")
    print(f"  Mock data: {USE_MOCK_DATA}")
