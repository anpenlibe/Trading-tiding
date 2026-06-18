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


def test_module_imports_without_kiteconnect(monkeypatch):
    """kiteconnect is imported lazily inside ZerodhaAPI.__init__, so the module
    must import and ZerodhaAPI must construct (unauthenticated) even if the
    package is unavailable."""
    monkeypatch.setitem(sys.modules, "kiteconnect", None)  # force ImportError on `import kiteconnect`
    api = ZerodhaAPI()
    assert api.is_available() is False  # degraded, not crashed
