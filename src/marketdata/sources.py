"""Concrete market-data source: ZerodhaAPI (live Kite Connect).

Zerodha is the SOLE live data source. The old yfinance fallback and the synthetic
MockAPI were removed: backtests read the local SQLite snapshot, and live/paper
collection requires a real Zerodha session — missing or expired credentials fail
loud rather than silently degrading to fabricated bars. kiteconnect is imported
lazily so this module loads even when it isn't installed.
"""

import os
from typing import Optional

import pandas as pd

from src.platform.types import BaseMarketDataAPI, MarketData
from src.platform.logger import setup_logger

logger = setup_logger('data_collector', 'data_collector.log')


class ZerodhaAPI(BaseMarketDataAPI):
    """Zerodha OHLC + Quote data using Kite Connect."""

    def __init__(self, **kwargs):
        self.kite = None
        self.is_authenticated = False

        try:
            # Force reload environment variables to get latest values
            from kiteconnect import KiteConnect
            from dotenv import load_dotenv
            if os.path.exists('.env'):
                load_dotenv('.env', override=True)

            self.api_key = os.getenv("ZERODHA_API_KEY", "")
            self.api_secret = os.getenv("ZERODHA_API_SECRET", "")
            self.access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "")

            if self.api_key and self.access_token:
                self.kite = KiteConnect(api_key=self.api_key)
                self.kite.set_access_token(self.access_token)

                # Test authentication with a permission-free call.
                try:
                    instruments = self.kite.instruments()
                    if len(instruments) > 0:
                        self.is_authenticated = True
                        logger.info("Zerodha API authenticated successfully")
                    else:
                        raise Exception("No instruments data received")
                except Exception as e:
                    if "permission" in str(e).lower():
                        logger.warning(f"Zerodha API limited permissions: {e}")
                    else:
                        logger.warning(f"Zerodha authentication failed: {e}")
                    self.is_authenticated = False
            else:
                logger.info("Zerodha credentials not configured")
                self.is_authenticated = False

        except ImportError:
            logger.warning("kiteconnect not installed - Zerodha unavailable")
            self.is_authenticated = False
        except Exception as e:
            logger.error(f"Zerodha initialization error: {e}")
            self.is_authenticated = False

        # Preload instrument token mappings only if authenticated.
        self.tokens = self._load_token_map() if self.is_authenticated else {}

    def _load_token_map(self) -> dict:
        """Load instrument token mappings from instruments.csv"""
        try:
            df = pd.read_csv("instruments.csv")
            df = df[df["exchange"] == "NSE"]
            return dict(zip(df["tradingsymbol"], df["instrument_token"]))
        except Exception as e:
            logger.warning(f"Failed to load instrument tokens: {e}")
            return {}

    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Fetch current OHLC + volume for the given symbol using Zerodha."""
        try:
            token = self.tokens.get(symbol)
            if not token:
                logger.warning(f"Token not found for {symbol}")
                return None

            token_str = str(token)
            ohlc_data = self.kite.ohlc([token])
            quote_data = self.kite.quote([token])

            if token_str not in ohlc_data or token_str not in quote_data:
                logger.error(f"Token missing in Zerodha response for {symbol}")
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
            logger.error(f"Zerodha fetch failed for {symbol}: {e}")
            return None

    def is_available(self) -> bool:
        return self.is_authenticated

    def get_name(self) -> str:
        return "Zerodha" if self.is_authenticated else "Zerodha(Unauthenticated)"
