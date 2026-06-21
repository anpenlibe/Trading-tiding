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

                # Verify the access token with a cheap authenticated call. profile()
                # returns a small user object and needs a valid session — unlike
                # instruments(), which downloads the entire multi-MB instrument dump
                # on every construction just to prove auth (the token map is loaded
                # separately from instruments.csv, so that download was discarded).
                try:
                    profile = self.kite.profile()
                    if profile:
                        self.is_authenticated = True
                        logger.info(f"Zerodha API authenticated ({profile.get('user_name', 'user')})")
                    else:
                        raise Exception("Empty profile response")
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
        """Fetch the current bar for ``symbol`` from Zerodha's full quote.

        The bar's CLOSE is the live ``last_price``, NOT the quote's ``ohlc.close``:
        Kite populates ``ohlc.close`` with the PREVIOUS trading day's settled close,
        so using it would price every live decision and paper fill off yesterday's
        number (and, because that stale close sits outside today's gapped range,
        trip the OHLC-consistency validator on gap days). ``open/high/low`` come from
        today's ``ohlc`` block; high/low are widened to include ``last_price`` so the
        bar stays internally consistent even on a fresh extreme tick.

        One ``quote()`` call carries the OHLC block, ``last_price`` AND ``volume``
        (a superset of ``ohlc()``), so it replaces the previous two-call fetch.
        """
        try:
            token = self.tokens.get(symbol)
            if not token:
                logger.warning(f"Token not found for {symbol}")
                return None

            token_str = str(token)
            quote_data = self.kite.quote([token])
            if token_str not in quote_data:
                logger.error(f"Token missing in Zerodha quote response for {symbol}")
                return None

            q = quote_data[token_str]
            last_price = q.get("last_price")
            if not last_price:
                logger.error(f"No last_price in Zerodha quote for {symbol}")
                return None

            ohlc = q.get("ohlc") or {}
            day_open = ohlc.get("open", last_price)
            day_high = max(ohlc.get("high", last_price), last_price)
            day_low = min(ohlc.get("low", last_price), last_price)

            timestamp = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)

            return MarketData(
                symbol=symbol,
                timestamp=timestamp,
                open=day_open,
                high=day_high,
                low=day_low,
                close=last_price,        # live LTP, not the prior-day settle
                volume=int(q.get("volume") or 0),
                source="zerodha",
            )

        except Exception as e:
            logger.error(f"Zerodha fetch failed for {symbol}: {e}")
            return None

    def is_available(self) -> bool:
        return self.is_authenticated

    def get_name(self) -> str:
        return "Zerodha" if self.is_authenticated else "Zerodha(Unauthenticated)"
