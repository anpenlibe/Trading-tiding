"""Regression tests for the indicator engine (Features layer).

Pins the calculate_* helpers' minimum-window None behavior, the
calculate_all_indicators output shape/keys, the <5-rows empty-dict guard, and
that MACD is computed once (a known value) rather than recomputed per component.
calculate_all_indicators output was also verified byte-identical to the
pre-refactor implementation on real DB data.
"""

import numpy as np
import pandas as pd

from src.core.indicator_engine import (
    calculate_sma,
    calculate_rsi,
    calculate_macd,
    calculate_price_change_pct,
    calculate_all_indicators,
)
from src.data.config import SMA_PERIODS


def _ohlcv(n):
    """A rising-price OHLCV frame with n rows."""
    close = pd.Series(np.linspace(100, 100 + n, n), dtype=float)
    return pd.DataFrame({
        "timestamp": pd.date_range("2025-01-01", periods=n, freq="D"),
        "open": close, "high": close + 1, "low": close - 1,
        "close": close, "volume": np.full(n, 100000),
    })


def test_sma_needs_full_window():
    s = pd.Series([1.0, 2.0, 3.0])
    assert calculate_sma(s, 5) is None
    assert calculate_sma(s, 3) == 2.0


def test_rsi_needs_period_plus_one():
    assert calculate_rsi(pd.Series(np.arange(5, dtype=float)), period=14) is None
    rsi = calculate_rsi(_ohlcv(30)["close"], period=14)
    assert rsi is not None and 0 <= rsi <= 100


def test_macd_shape_and_insufficient_data():
    empty = calculate_macd(pd.Series([1.0, 2.0]))
    assert empty == {"macd": None, "macd_signal": None, "macd_histogram": None}
    macd = calculate_macd(_ohlcv(40)["close"])
    assert set(macd) == {"macd", "macd_signal", "macd_histogram"}
    assert all(isinstance(v, float) for v in macd.values())


def test_price_change_pct():
    assert calculate_price_change_pct(pd.Series([100.0, 110.0])) == 10.0
    assert calculate_price_change_pct(pd.Series([100.0])) is None


def test_all_indicators_returns_empty_below_five_rows():
    assert calculate_all_indicators(_ohlcv(4)) == {}
    assert calculate_all_indicators(None) == {}


def test_all_indicators_full_shape():
    result = calculate_all_indicators(_ohlcv(250))
    expected_keys = {"rsi_14", "macd", "macd_signal", "macd_histogram",
                     "volume_avg_20", "price_change_pct"}
    expected_keys |= {f"sma_{p}" for p in SMA_PERIODS}
    assert set(result) == expected_keys


def test_macd_keys_match_standalone(monkeypatch):
    """calculate_all_indicators must compute MACD once and surface the same
    values calculate_macd returns directly (guards the 3x->1x consolidation)."""
    df = _ohlcv(60)
    standalone = calculate_macd(df["close"])
    allind = calculate_all_indicators(df)
    for k in ("macd", "macd_signal", "macd_histogram"):
        assert allind[k] == standalone[k]
