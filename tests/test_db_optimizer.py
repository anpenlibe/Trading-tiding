"""Regression tests for DatabaseOptimizer.

Exercises the optimizer against an isolated temp SQLite DB (never the bundled
snapshot or runtime DB). Pins index creation idempotency, performance metrics,
the WAL pragma, and the *destructive* cleanup_old_data retention boundary.
"""

import sqlite3

import pytest

from src.utils.db_optimizer import DatabaseOptimizer


@pytest.fixture
def temp_db(tmp_path):
    path = tmp_path / "opt.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE price_data (symbol TEXT, timestamp TEXT, close REAL)")
    conn.execute("CREATE TABLE indicators (symbol TEXT, timestamp TEXT, indicator_name TEXT)")
    conn.execute("CREATE TABLE data_quality_log (symbol TEXT, timestamp TEXT)")
    conn.executemany("INSERT INTO price_data VALUES (?, ?, ?)", [
        ("TCS", "2020-01-01 00:00:00", 100.0),   # older than any retention window
        ("TCS", "2099-01-01 00:00:00", 200.0),   # far future, always retained
    ])
    conn.commit()
    conn.close()
    return str(path)


def test_analyze_performance_reports_tables_and_size(temp_db):
    opt = DatabaseOptimizer(temp_db)
    metrics = opt.analyze_performance()
    opt.close()
    assert metrics["size_mb"] > 0
    assert metrics["tables"]["price_data"] == 2
    assert metrics["tables"]["indicators"] == 0


def test_optimize_indexes_is_idempotent(temp_db):
    opt = DatabaseOptimizer(temp_db)
    first = opt.optimize_indexes()
    second = opt.optimize_indexes()
    opt.close()
    assert any("idx_price_symbol_timestamp" in line for line in first)
    assert second == []  # already created on the first pass


def test_cleanup_old_data_removes_only_old_rows(temp_db):
    opt = DatabaseOptimizer(temp_db)
    deleted = opt.cleanup_old_data(days_to_keep=90)
    remaining = opt.conn.execute("SELECT COUNT(*) FROM price_data").fetchone()[0]
    opt.close()
    assert deleted == 1     # only the 2020 row is past the cutoff
    assert remaining == 1   # the 2099 row survives


def test_optimize_settings_enables_wal(temp_db):
    opt = DatabaseOptimizer(temp_db)
    opt.optimize_settings()  # must not raise
    mode = opt.conn.execute("PRAGMA journal_mode").fetchone()[0]
    opt.close()
    assert mode.lower() == "wal"
