"""Regression tests for the shared interface layer.

Pins:
- MarketData.to_dict serialization shape (timestamp as ISO-8601 string).
- The Base* contracts remain abstract (cannot be instantiated directly).
- TradingSignal, removed during cleanup (zero references; signals flow as plain
  dicts), does not creep back. Re-add it deliberately if a later phase adopts a
  typed signal.
"""

from datetime import datetime

import pytest

import src.interfaces as interfaces
from src.interfaces import (
    MarketData,
    BaseMarketDataAPI,
    BaseDecisionModel,
    BaseRiskManager,
    BaseTradingExecutor,
)


def test_market_data_to_dict_shape():
    bar = MarketData(
        symbol="TCS",
        timestamp=datetime(2025, 11, 10, 10, 0, 0),
        open=1.0, high=2.0, low=0.5, close=1.5, volume=100,
    )
    d = bar.to_dict()
    assert d["symbol"] == "TCS"
    assert d["timestamp"] == "2025-11-10T10:00:00.000000"
    assert (d["open"], d["high"], d["low"], d["close"], d["volume"]) == (1.0, 2.0, 0.5, 1.5, 100)
    assert d["source"] == "unknown"  # default


@pytest.mark.parametrize("abc_cls", [
    BaseMarketDataAPI,
    BaseDecisionModel,
    BaseRiskManager,
    BaseTradingExecutor,
])
def test_base_contracts_are_abstract(abc_cls):
    with pytest.raises(TypeError):
        abc_cls()


def test_trading_signal_stays_removed():
    assert not hasattr(interfaces, "TradingSignal"), (
        "TradingSignal had zero references; re-add only if a typed signal is adopted."
    )
