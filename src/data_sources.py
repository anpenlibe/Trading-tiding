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
from src.config import MOCK_VOLUME_RANGE_MIN, MOCK_VOLUME_RANGE_MAX

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
            self.api_key = os.getenv("ZERODHA_API_KEY", "")
            self.api_secret = os.getenv("ZERODHA_API_SECRET", "")
            self.access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "")
            
            if self.api_key and self.access_token:
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.access_token)
                
                # Test authentication with a simple call
                try:
                    self.kite.profile()
                    self.is_authenticated = True
                    logger.logger.info("Zerodha API authenticated successfully")
                except Exception as e:
                    logger.logger.warning(f"Zerodha authentication failed: {e}")
                    logger.logger.info("Will use MockAPI as fallback")
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
        
        if symbol not in self.base_prices:
            return None
        
        base = self.base_prices[symbol]
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
