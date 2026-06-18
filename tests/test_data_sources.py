"""Regression tests for the market-data sources.

Pins MockAPI's contract (always available, valid OHLC for known + unknown
symbols, naive timestamp), that all three sources satisfy BaseMarketDataAPI,
and that kiteconnect is imported lazily (module loads without it; a missing
kiteconnect degrades ZerodhaAPI to unauthenticated rather than crashing import).
"""

import sys

import pytest

from src.interfaces import BaseMarketDataAPI, MarketData
from src.data.data_sources import MockAPI, YahooFinanceAPI, ZerodhaAPI


def test_all_sources_are_marketdata_apis():
    assert issubclass(MockAPI, BaseMarketDataAPI)
    assert issubclass(YahooFinanceAPI, BaseMarketDataAPI)
    assert issubclass(ZerodhaAPI, BaseMarketDataAPI)


def test_mock_always_available_and_named():
    api = MockAPI()
    assert api.is_available() is True
    assert api.get_name() == "mock"


@pytest.mark.parametrize("symbol", ["TCS", "UNKNOWN_SYMBOL"])
def test_mock_returns_valid_ohlc(symbol):
    bar = MockAPI().fetch_ohlc(symbol)
    assert isinstance(bar, MarketData)
    assert bar.symbol == symbol
    assert bar.source == "mock"
    # OHLC must be internally consistent and positive.
    assert bar.high >= bar.open and bar.high >= bar.close
    assert bar.low <= bar.open and bar.low <= bar.close
    assert bar.volume > 0
    assert bar.timestamp.tzinfo is None  # naive, for DB compatibility


def test_mock_base_anchored_to_snapshot():
    """MockAPI bars must sit near the symbol's real last close (within the ~1%
    variation band), not a stale hardcoded base. Pins the RSI-artifact fix where
    RELIANCE's hardcoded 2850 vs a real ~1566 teleported price +82%."""
    import sqlite3
    from src.data.config import BUNDLED_DB_PATH
    conn = sqlite3.connect(BUNDLED_DB_PATH)
    real = conn.execute(
        "SELECT close FROM price_data WHERE symbol='RELIANCE' ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()[0]
    conn.close()
    bar = MockAPI().fetch_ohlc("RELIANCE")
    assert abs(bar.close - real) / real < 0.05  # was ~0.82 with the stale base


def test_mock_unknown_symbol_uses_default_base():
    bar = MockAPI().fetch_ohlc("NONEXISTENT_XYZ")
    assert bar is not None and bar.close > 0  # default base, no crash


def test_module_imports_without_kiteconnect(monkeypatch):
    """kiteconnect is imported lazily inside ZerodhaAPI.__init__, so the module
    must import and ZerodhaAPI must construct (unauthenticated) even if the
    package is unavailable."""
    monkeypatch.setitem(sys.modules, "kiteconnect", None)  # force ImportError on `import kiteconnect`
    api = ZerodhaAPI()
    assert api.is_available() is False  # degraded, not crashed
