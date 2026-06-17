"""
Module: data_sources.py
Purpose: Concrete implementations of market data APIs using interfaces
Author: Trading Bot Developer
Created: 2025-06-13
Modified: 2025-06-30 - Fixed interface compliance
"""

import os
import time
from datetime import datetime, timedelta
import json
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime, timezone

from src.interfaces import BaseMarketDataAPI, MarketData
from src.utils.logger import get_data_logger
from src.data.config import MOCK_VOLUME_RANGE_MIN, MOCK_VOLUME_RANGE_MAX

logger = get_data_logger()

from kiteconnect import KiteConnect
import pandas as pd
from datetime import timezone

class ZerodhaAPI(BaseMarketDataAPI):
    """Zerodha OHLC + Quote Data using Kite Connect"""

    def __init__(self, **kwargs):  # FIXED: Now accepts **kwargs as per interface
        self.kite = None
        self.is_authenticated = False
        
        try:
            # Force reload environment variables to get latest values
            from dotenv import load_dotenv
            if os.path.exists('.env'):
                load_dotenv('.env', override=True)
            
            self.api_key = os.getenv("ZERODHA_API_KEY", "")
            self.api_secret = os.getenv("ZERODHA_API_SECRET", "")
            self.access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "")
            
            if self.api_key and self.access_token:
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.access_token)
                
                # Test authentication with a permission-free call
                try:
                    # Use instruments() call which works with basic API access
                    instruments = self.kite.instruments()
                    if len(instruments) > 0:
                        self.is_authenticated = True
                        logger.logger.info("Zerodha API authenticated successfully")
                    else:
                        raise Exception("No instruments data received")
                except Exception as e:
                    # Check if it's a permission issue vs auth issue
                    if "permission" in str(e).lower():
                        logger.logger.warning(f"Zerodha API limited permissions: {e}")
                        logger.logger.info("Basic auth successful but market data restricted")
                        # Still mark as unauthenticated for market data purposes
                        self.is_authenticated = False
                    else:
                        logger.logger.warning(f"Zerodha authentication failed: {e}")
                    logger.logger.info("Will use fallback APIs for market data")
                    self.is_authenticated = False
            else:
                logger.logger.info("Zerodha credentials not configured - using MockAPI")
                self.is_authenticated = False
                
        except ImportError:
            logger.logger.warning("kiteconnect not installed - using MockAPI")
            self.is_authenticated = False
        except Exception as e:
            logger.logger.error(f"Zerodha initialization error: {e}")
            self.is_authenticated = False

        # Preload instrument token mappings only if authenticated
        self.tokens = self._load_token_map() if self.is_authenticated else {}

    def _load_token_map(self) -> dict:
        """Load instrument token mappings from instruments.csv"""
        try:
            df = pd.read_csv("instruments.csv")
            df = df[df["exchange"] == "NSE"]
            return dict(zip(df["tradingsymbol"], df["instrument_token"]))
        except Exception as e:
            logger.logger.warning(f"Failed to load instrument tokens: {e}")
            return {}

    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Fetch current OHLC + volume for the given symbol using Zerodha"""
        try:
            token = self.tokens.get(symbol)
            if not token:
                logger.logger.warning(f"Token not found for {symbol}")
                return None

            token_str = str(token)
            ohlc_data = self.kite.ohlc([token])
            quote_data = self.kite.quote([token])

            if token_str not in ohlc_data or token_str not in quote_data:
                logger.logger.error(f"Token missing in Zerodha response for {symbol}")
                return None

            ohlc = ohlc_data[token_str]["ohlc"]
            volume = quote_data[token_str].get("volume", -1)

            timestamp = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)

            return MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=ohlc["open"],
                high=ohlc["high"],
                low=ohlc["low"],
                close=ohlc["close"],
                volume=int(volume),
                source="zerodha"
            )

        except Exception as e:
            logger.logger.error(f"Zerodha fetch failed for {symbol}: {e}")
            return None
 

    def is_available(self) -> bool:
        return self.is_authenticated

    def get_name(self) -> str:
        return "Zerodha" if self.is_authenticated else "Zerodha(Unauthenticated)"

class MockAPI(BaseMarketDataAPI):
    """Mock API for testing during market closed hours"""
    
    def __init__(self, **kwargs):  # FIXED: Now accepts **kwargs as per interface
        self.base_prices = {
            "RELIANCE": 2850,
            "TCS": 3650,
            "INFY": 1450,
            "HDFC": 1650,
            "ICICIBANK": 980,
            "SBIN": 1100,
            "BHARTIARTL": 950,
            "ITC": 440,
            "KOTAKBANK": 1750,
            "LT": 3200
        }
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Generate mock data with realistic variations"""
        import random

        # Unknown symbols still get synthetic data so paper/test runs aren't
        # starved (mock is for pipeline testing, not realism).
        base = self.base_prices.get(symbol, 1000.0)
        variation = base * 0.01  # 1% variation
        
        # Generate realistic OHLC
        open_price = base + random.uniform(-variation, variation)
        
        # Ensure high is highest and low is lowest
        intraday_moves = [open_price]
        for _ in range(5):  # Simulate some price movements
            intraday_moves.append(open_price + random.uniform(-variation, variation))
        
        high = max(intraday_moves)
        low = min(intraday_moves)
        close = intraday_moves[-1]  # Last price becomes close
        
        # FIXED: Use naive datetime without timezone for database compatibility
        timestamp = datetime.now().replace(microsecond=0)
        
        return MarketData(
            symbol=symbol,
            timestamp=timestamp,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close, 2),
            volume=random.randint(MOCK_VOLUME_RANGE_MIN, MOCK_VOLUME_RANGE_MAX),
            source="mock"
        )
    
    def is_available(self) -> bool:
        """Mock is always available"""
        return True
    
    def get_name(self) -> str:  # FIXED: Added missing method
        return "mock"


class YahooFinanceAPI(BaseMarketDataAPI):
    """Yahoo Finance fallback data source for NSE stocks with rate limiting."""
    
    def __init__(self, **kwargs):
        """Initialize Yahoo Finance API with rate limiting."""
        self.name = "YahooFinance"
        self.is_live = True  # Can provide live data
        
        # Rate limiting configuration
        self.last_request_time = 0
        self.min_request_interval = 2.0  # Minimum 2 seconds between requests
        self.retry_count = 0
        self.max_retries = 3
        self.backoff_base = 5  # Base backoff time in seconds
        self.rate_limited_until = 0  # Timestamp when rate limiting ends
        
        # Import yfinance here to avoid dependency issues if not available
        try:
            import yfinance as yf
            import time
            self.yf = yf
            self.time = time
            logger.logger.info("Yahoo Finance API initialized with rate limiting")
        except ImportError:
            self.yf = None
            logger.logger.warning("yfinance not installed - Yahoo Finance API unavailable")
    
    def get_name(self) -> str:
        return self.name
    
    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        if not self.yf:
            return
        
        current_time = self.time.time()
        
        # Check if we're in a rate limit cooldown period
        if current_time < self.rate_limited_until:
            wait_time = self.rate_limited_until - current_time
            logger.logger.info(f"Yahoo Finance: Waiting {wait_time:.1f}s due to rate limiting")
            self.time.sleep(wait_time)
            return
        
        # Normal rate limiting
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            logger.logger.debug(f"Yahoo Finance: Rate limiting - waiting {wait_time:.1f}s")
            self.time.sleep(wait_time)
        
        self.last_request_time = self.time.time()
    
    def _handle_rate_limit_error(self, error_msg: str):
        """Handle 429 rate limit errors with exponential backoff."""
        if "429" in str(error_msg) or "Too Many Requests" in str(error_msg):
            self.retry_count += 1
            backoff_time = self.backoff_base * (2 ** (self.retry_count - 1))  # Exponential backoff
            
            # Set rate limited until timestamp
            self.rate_limited_until = self.time.time() + backoff_time
            
            logger.logger.warning(f"Yahoo Finance: Rate limited (attempt {self.retry_count}/{self.max_retries}). "
                                f"Backing off for {backoff_time}s")
            
            if self.retry_count >= self.max_retries:
                logger.logger.error("Yahoo Finance: Max retries exceeded. Disabling for this session.")
                return False
            
            return True  # Can retry
        
        return False  # Different error, don't retry
    
    def is_available(self) -> bool:
        """Check if Yahoo Finance is accessible with rate limiting."""
        if not self.yf:
            return False
        
        # If we've hit max retries, consider unavailable
        if self.retry_count >= self.max_retries:
            return False
        
        # If we're in rate limit cooldown, consider temporarily unavailable
        current_time = self.time.time()
        if current_time < self.rate_limited_until:
            return False
        
        try:
            self._wait_for_rate_limit()
            
            # Use a simple test that's less likely to be rate limited
            # Try to create a ticker object and check if it exists
            ticker = self.yf.Ticker("RELIANCE.NS")
            
            # Get minimal data to test availability without heavy API calls
            try:
                # Just get the ticker info without full history
                info = ticker.fast_info
                return True
            except:
                # Fallback to basic ticker creation test
                hist = ticker.history(period="1d", interval="1d")  # Less frequent data
                return not hist.empty
                
        except Exception as e:
            error_msg = str(e)
            logger.logger.debug(f"Yahoo Finance availability test failed: {error_msg}")
            
            # Handle rate limiting
            if self._handle_rate_limit_error(error_msg):
                return False  # Temporarily unavailable due to rate limiting
            
            # Other errors - consider permanently unavailable for this session
            logger.logger.warning(f"Yahoo Finance not available: {error_msg}")
            return False
    
    def fetch_ohlc(self, symbol: str, interval: str = "5m") -> Optional[MarketData]:
        """Fetch OHLC data from Yahoo Finance for NSE stocks with rate limiting."""
        if not self.yf:
            return None
        
        # Check if we're available (handles rate limiting)
        if not self.is_available():
            logger.logger.debug(f"Yahoo Finance temporarily unavailable for {symbol}")
            return None
        
        try:
            # Enforce rate limiting
            self._wait_for_rate_limit()
            
            # Convert symbol to Yahoo format (add .NS for NSE)
            yahoo_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            
            # Map intervals to Yahoo Finance format
            interval_map = {
                "1m": "1m",
                "5m": "5m", 
                "15m": "15m",
                "30m": "30m",
                "1h": "60m",
                "1d": "1d"
            }
            
            yahoo_interval = interval_map.get(interval, "5m")
            
            # Fetch data with retry logic
            ticker = self.yf.Ticker(yahoo_symbol)
            
            # Use more conservative periods to reduce API load
            if interval in ["1m", "5m", "15m", "30m"]:
                period = "1d"  # Intraday data
            else:
                period = "2d"  # Reduce from 5d to 2d for daily data
            
            hist = ticker.history(period=period, interval=yahoo_interval)
            
            if hist.empty:
                logger.logger.debug(f"No data from Yahoo for {symbol}")
                return None
            
            # Get latest row
            latest = hist.iloc[-1]
            latest_time = hist.index[-1]
            
            # Convert timezone-aware timestamp to naive for database compatibility
            if hasattr(latest_time, 'tz_localize'):
                timestamp = latest_time.tz_localize(None)
            else:
                timestamp = latest_time.replace(tzinfo=None) if latest_time.tzinfo else latest_time
            
            # Reset retry count on successful fetch
            self.retry_count = 0
            
            return MarketData(
                symbol=symbol,  # Use original symbol format
                timestamp=timestamp,
                open=float(latest['Open']),
                high=float(latest['High']),
                low=float(latest['Low']),
                close=float(latest['Close']),
                volume=int(latest['Volume']),
                source="yahoo"
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.logger.debug(f"Yahoo Finance fetch error for {symbol}: {error_msg}")
            
            # Handle rate limiting errors
            if self._handle_rate_limit_error(error_msg):
                logger.logger.info(f"Yahoo Finance rate limited for {symbol}, will retry later")
                return None
            
            # For other errors, log and return None
            logger.logger.warning(f"Yahoo Finance error for {symbol}: {error_msg}")
            return None
    
    def fetch_historical(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Fetch historical data from Yahoo Finance with rate limiting."""
        if not self.yf:
            return None
        
        # Check if we're available (handles rate limiting)
        if not self.is_available():
            logger.logger.debug(f"Yahoo Finance temporarily unavailable for historical {symbol}")
            return None
        
        try:
            # Enforce rate limiting
            self._wait_for_rate_limit()
            
            yahoo_symbol = f"{symbol}.NS" if not symbol.endswith('.NS') else symbol
            ticker = self.yf.Ticker(yahoo_symbol)
            
            # Use period instead of start/end dates to reduce API complexity
            if days <= 7:
                period = "7d"
            elif days <= 30:
                period = "1mo"
            elif days <= 90:
                period = "3mo"
            else:
                period = "6mo"
            
            hist = ticker.history(period=period, interval="1d")
            
            if hist.empty:
                logger.logger.debug(f"No historical data from Yahoo for {symbol}")
                return None
            
            # Limit to requested days
            if len(hist) > days:
                hist = hist.tail(days)
            
            # Rename columns to match our schema and convert timezone
            hist = hist.rename(columns={
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            hist['symbol'] = symbol
            
            # Convert timezone-aware index to naive timestamps
            hist['timestamp'] = hist.index.tz_localize(None) if hist.index.tz else hist.index
            
            # Reset retry count on successful fetch
            self.retry_count = 0
            
            return hist[['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)
            
        except Exception as e:
            error_msg = str(e)
            logger.logger.debug(f"Yahoo historical fetch error for {symbol}: {error_msg}")
            
            # Handle rate limiting errors
            if self._handle_rate_limit_error(error_msg):
                logger.logger.info(f"Yahoo Finance rate limited for historical {symbol}, will retry later")
                return None
            
            # For other errors, log and return None
            logger.logger.warning(f"Yahoo historical error for {symbol}: {error_msg}")
            return None
