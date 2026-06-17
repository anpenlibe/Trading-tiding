"""Regression tests for runtime/bundled DB isolation.

Pins the fix for the pollution bug: running the trader/collector used to write
live/mock bars straight into the committed snapshot (DB_PATH == BUNDLED_DB_PATH).
Now runtime writes go to a separate, gitignored DB seeded from the snapshot.
"""

import os
import sqlite3

from src.data.config import DB_PATH, BUNDLED_DB_PATH
from src.data.database import DatabaseManager
from src.interfaces import MarketData


def test_runtime_and_bundled_paths_differ():
    assert os.path.abspath(DB_PATH) != os.path.abspath(BUNDLED_DB_PATH)


def test_seeds_runtime_db_into_temp(tmp_path):
    runtime = tmp_path / "runtime.sqlite"
    db = DatabaseManager(str(runtime))
    try:
        assert runtime.exists(), "runtime DB should be seeded from the bundled snapshot"
        # seeded copy carries the historical rows
        n = db.conn.execute("SELECT COUNT(*) FROM price_data").fetchone()[0]
        assert n > 0
    finally:
        db.close()


def test_writes_do_not_touch_bundled_snapshot(tmp_path):
    """A write through a runtime DB must not change the bundled snapshot file."""
    before_mtime = os.path.getmtime(BUNDLED_DB_PATH)
    before_count = sqlite3.connect(BUNDLED_DB_PATH).execute(
        "SELECT COUNT(*) FROM price_data"
    ).fetchone()[0]

    db = DatabaseManager(str(tmp_path / "runtime.sqlite"))
    try:
        db.save_market_data(MarketData(
            symbol="TESTSYM", timestamp="2026-06-18T10:00:00",
            open=1.0, high=2.0, low=0.5, close=1.5, volume=1000, source="mock",
        ))
    finally:
        db.close()

    after_count = sqlite3.connect(BUNDLED_DB_PATH).execute(
        "SELECT COUNT(*) FROM price_data"
    ).fetchone()[0]
    assert after_count == before_count
    assert os.path.getmtime(BUNDLED_DB_PATH) == before_mtime
