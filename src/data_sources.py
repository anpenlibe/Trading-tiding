"""
Module: data_sources.py
Purpose: Concrete implementations of market data APIs using interfaces
Author: Trading Bot Developer
Created: 2025-06-13
Modified: 2025-06-13
"""

import os
import time
import requests
import yfinance as yf
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd

from src.interfaces import BaseMarketDataAPI, MarketData
from src.utils.logger import get_data_logger

logger = get_data_logger()


class DhanAPI(BaseMarketDataAPI):
    """Dhan API implementation"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv('DHAN_API_KEY')
        self.base_url = "https://api.dhan.co"
        
        if self.access_token:
            self.headers = {
                "access-token": self.access_token,
                "Content-Type": "application/json"
            }
            logger.logger.info("Dhan API initialized with token")
        else:
            self.headers = {}
            logger.logger.warning("Dhan API key not found")
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Fetch OHLC data from Dhan API"""
        if not self.is_available():
            return None
            
        try:
            start_time = time.time()
            today = datetime.now().strftime('%Y-%m-%d')

            params = {
                "symbol": f"{symbol}-EQ",  # Dhan format: RELIANCE-EQ
                "exchange": "NSE",         # Modify if needed for BSE
                "interval": "5MIN",
                "fromDate": today,
                "toDate": today
            }

            response = requests.get(
                f"{self.base_url}/market/intraday/candle",
                headers=self.headers,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.log_api_call("dhan", symbol, False,
                                    time.time() - start_time,
                                    f"HTTP {response.status_code}")
                return None

             # Get the latest candle
            latest = data["candle"][-1]

            market_data = MarketData(
                symbol=symbol,
                timestamp=datetime.strptime(latest["startTime"], "%Y-%m-%d %H:%M:%S"),
                open=float(latest["open"]),
                high=float(latest["high"]),
                low=float(latest["low"]),
                close=float(latest["close"]),
                volume=int(latest["volume"]),
                source="dhan"
            )

            duration = time.time() - start_time
            logger.log_api_call("dhan", symbol, True, duration)

            return market_data

        except Exception as e:
        duration = time.time() - start_time
        logger.log_api_call("dhan", symbol, False, duration, str(e))
        return None

    def is_available(self) -> bool:
        """Check if Dhan API is configured"""
        return bool(self.access_token)


class YFinanceAPI(BaseMarketDataAPI):
    """Yahoo Finance implementation"""
    
    def __init__(self):
        # yfinance doesn't need initialization
        pass
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Fetch OHLC data from Yahoo Finance"""
        try:
            start_time = time.time()
            
            # Add .NS suffix for NSE stocks
            ticker_symbol = f"{symbol}.NS"
            ticker = yf.Ticker(ticker_symbol)
            
            # Get intraday data (5 minute intervals)
            hist = ticker.history(period="1d", interval="5m")
            
            if hist.empty:
                logger.log_api_call("yfinance", symbol, False, 
                                  time.time() - start_time, "No data returned")
                return None
            
            # Get the latest row
            latest = hist.iloc[-1]
            
            # Create MarketData object
            data = MarketData(
                symbol=symbol,
                timestamp=hist.index[-1].to_pydatetime(),
                open=float(latest['Open']),
                high=float(latest['High']),
                low=float(latest['Low']),
                close=float(latest['Close']),
                volume=int(latest['Volume']),
                source="yfinance"
            )
            
            duration = time.time() - start_time
            logger.log_api_call("yfinance", symbol, True, duration)
            
            return data
            
        except Exception as e:
            duration = time.time() - start_time
            logger.log_api_call("yfinance", symbol, False, duration, str(e))
            return None
    
    def is_available(self) -> bool:
        """yfinance is always available"""
        return True


class TwelveDataAPI(BaseMarketDataAPI):
    """Twelve Data implementation"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('TWELVE_DATA_API_KEY')
        self.base_url = "https://api.twelvedata.com"
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Fetch OHLC data from Twelve Data"""
        if not self.is_available():
            return None
        
        try:
            start_time = time.time()
            
            params = {
                "symbol": symbol,
                "exchange": "NSE",
                "interval": "5min",
                "outputsize": 1,
                "apikey": self.api_key
            }
            
            response = requests.get(
                f"{self.base_url}/time_series",
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.log_api_call("twelve_data", symbol, False, 
                                  time.time() - start_time, 
                                  f"HTTP {response.status_code}")
                return None
            
            data = response.json()
            if "values" not in data or not data["values"]:
                logger.log_api_call("twelve_data", symbol, False, 
                                  time.time() - start_time, 
                                  "No values in response")
                return None
            
            # Get the latest data point
            latest = data["values"][0]
            
            market_data = MarketData(
                symbol=symbol,
                timestamp=datetime.strptime(latest["datetime"], "%Y-%m-%d %H:%M:%S"),
                open=float(latest["open"]),
                high=float(latest["high"]),
                low=float(latest["low"]),
                close=float(latest["close"]),
                volume=int(latest["volume"]),
                source="twelve_data"
            )
            
            duration = time.time() - start_time
            logger.log_api_call("twelve_data", symbol, True, duration)
            
            return market_data
            
        except Exception as e:
            duration = time.time() - start_time
            logger.log_api_call("twelve_data", symbol, False, duration, str(e))
            return None
    
    def is_available(self) -> bool:
        """Check if Twelve Data API is configured"""
        return bool(self.api_key)


class MockAPI(BaseMarketDataAPI):
    """Mock API for testing"""
    
    def __init__(self):
        self.base_prices = {
            "RELIANCE": 2850,
            "TCS": 3650,
            "INFY": 1450,
            "HDFC": 1650,
            "ICICIBANK": 980
        }
    
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Generate mock data"""
        import random
        
        if symbol not in self.base_prices:
            return None
        
        base = self.base_prices[symbol]
        variation = base * 0.01  # 1% variation
        
        open_price = base + random.uniform(-variation, variation)
        high = open_price + random.uniform(0, variation)
        low = open_price - random.uniform(0, variation)
        close = random.uniform(low, high)
        
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=random.randint(100000, 1000000),
            source="mock"
        )
    
    def is_available(self) -> bool:
        """Mock is always available"""
        return True
