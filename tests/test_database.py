"""Regression tests for DatabaseManager.

Pins the consolidated _to_timestamp_str normalization (the single funnel that
keeps the on-disk format as 'YYYY-MM-DD HH:MM:SS', which db_optimizer relies on),
a save/get round-trip, get_stats, and the removal of the dead methods
(insert_price_data, get_previous_close, log_data_quality_issue).
"""

from datetime import datetime, timezone

import pytest

from src.interfaces import MarketData
from src.data.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "db.sqlite"
    path.touch()  # exists -> _seed_from_bundled is a no-op (skips the 58MB copy)
    manager = DatabaseManager(str(path))
    yield manager
    manager.close()


@pytest.mark.parametrize("value,expected", [
    (datetime(2025, 11, 10, 10, 0, 0), "2025-11-10 10:00:00"),            # naive datetime
    (datetime(2025, 11, 10, 10, 0, 0, tzinfo=timezone.utc), "2025-11-10 10:00:00"),  # tz-aware -> naive
    ("2025-11-10T10:00:00.000000", "2025-11-10 10:00:00"),                # ISO 'T' string
    ("2025-11-10 10:00:00", "2025-11-10 10:00:00"),                       # already formatted
])
def test_timestamp_normalization(value, expected):
    assert DatabaseManager._to_timestamp_str(value) == expected


def test_save_and_get_round_trip(db):
    bar = MarketData("TCS", datetime(2025, 11, 10, 10, 0, 0), 100.0, 105.0, 99.0, 102.0, 1000)
    assert db.save_market_data(bar) is True
    df = db.get_recent_data("TCS", periods=10)
    assert len(df) == 1
    assert df.iloc[0]["close"] == 102.0


def test_save_indicators_and_stats(db):
    bar = MarketData("TCS", datetime(2025, 11, 10, 10, 0, 0), 100.0, 105.0, 99.0, 102.0, 1000)
    db.save_market_data(bar)
    db.save_indicators("TCS", datetime(2025, 11, 10, 10, 0, 0), {"sma_20": 101.0, "rsi_14": 55.0})
    stats = db.get_stats()
    assert stats["total_price_records"] == 1
    assert stats["total_indicator_records"] == 1
    assert stats["unique_symbols"] == 1


def test_removed_methods_stay_removed(db):
    for name in ("insert_price_data", "get_previous_close", "log_data_quality_issue"):
        assert not hasattr(db, name), f"{name} was dead and should stay removed"
