"""Regression tests for DataValidator.

Pins the validate() outcomes (valid, zero-price, high<low, low-volume,
price-change circuit breaker), the stats counters, and the removal of the dead
reset_stats / is_data_quality_good methods.
"""

from datetime import datetime

from src.interfaces import MarketData
from src.data.validator import DataValidator
from src.data.config import VALIDATION_MIN_VOLUME

GOOD_VOLUME = VALIDATION_MIN_VOLUME + 1000


def _bar(open=100.0, high=105.0, low=99.0, close=102.0, volume=GOOD_VOLUME):
    return MarketData("TCS", datetime(2025, 11, 10), open, high, low, close, volume)


def test_valid_bar_passes():
    ok, err = DataValidator().validate(_bar())
    assert ok and err is None


def test_zero_or_negative_price_rejected():
    ok, err = DataValidator().validate(_bar(low=0.0))
    assert not ok and "zero or negative" in err


def test_high_below_low_rejected():
    ok, err = DataValidator().validate(_bar(high=98.0, low=99.0))
    assert not ok and "less than low" in err


def test_low_volume_rejected():
    ok, err = DataValidator().validate(_bar(volume=0))
    assert not ok and "Volume too low" in err


def test_excessive_price_change_rejected():
    # A consistent bar at 200 vs a previous close of 100 = 100% jump.
    ok, err = DataValidator().validate(
        _bar(open=200.0, high=201.0, low=199.0, close=200.0), previous_close=100.0
    )
    assert not ok and "exceeds limit" in err


def test_get_stats_counts_outcomes():
    v = DataValidator()
    v.validate(_bar())          # valid
    v.validate(_bar(low=0.0))   # zero_price
    stats = v.get_stats()
    assert stats["valid"] == 1
    assert stats["zero_price"] == 1


def test_removed_methods_stay_removed():
    v = DataValidator()
    assert not hasattr(v, "reset_stats")
    assert not hasattr(v, "is_data_quality_good")
