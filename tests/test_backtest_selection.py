"""Tests for select_simulation_timestamps (runners/backtest.py).

The pure tick-selection helper: keep in-window bars, prefer intraday (>=10:00) but
fall back to daily, and space kept bars by CUMULATIVE timing (measured from the last
KEPT bar) so weekends/holidays don't desync the cadence — the bug the cumulative
approach was written to fix.
"""

import importlib.util
import pathlib

import pandas as pd

# Load runners/backtest.py by path (runners/ isn't an importable package). Its own
# top-level sys.path.append makes the `from src...` imports resolve during exec.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bt_runner", _ROOT / "runners" / "backtest.py")
_bt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bt)
select_simulation_timestamps = _bt.select_simulation_timestamps


def _ts(*items):
    return [pd.Timestamp(x) for x in items]


def test_intraday_filters_pre_open_and_spaces_cumulatively():
    bars = _ts("2025-06-02 09:15", "2025-06-02 09:30", "2025-06-02 10:00",
               "2025-06-02 10:15", "2025-06-02 10:30", "2025-06-02 11:00")
    picked = select_simulation_timestamps(bars, "2025-06-02", "2025-06-02", 30)
    # 09:15/09:30 dropped (pre-10:00). From 10:00: 10:15 is only 15min -> skipped;
    # 10:30 (30 from 10:00) and 11:00 (30 from 10:30) kept.
    assert picked == _ts("2025-06-02 10:00", "2025-06-02 10:30", "2025-06-02 11:00")


def test_window_bounds_are_inclusive_and_exclusive_dates_dropped():
    bars = _ts("2025-06-01 10:00", "2025-06-02 10:00", "2025-06-03 10:00")
    picked = select_simulation_timestamps(bars, "2025-06-02", "2025-06-02", 30)
    assert picked == _ts("2025-06-02 10:00")


def test_daily_fallback_when_no_intraday_bars():
    # Pure-daily snapshot: one midnight bar per day, none >=10:00 -> fallback keeps them.
    bars = _ts("2025-06-02 00:00", "2025-06-03 00:00", "2025-06-04 00:00")
    picked = select_simulation_timestamps(bars, "2025-06-02", "2025-06-04", 1440)
    assert picked == bars


def test_cumulative_spacing_survives_a_weekend_gap():
    # Fri then Mon (weekend gap). Cumulative spacing from the last KEPT bar means the
    # Monday bar's 3-day gap easily clears the 1-day interval and is kept — exact
    # modulo alignment would have desynced here.
    bars = _ts("2025-06-06 00:00", "2025-06-09 00:00")  # Fri, Mon
    picked = select_simulation_timestamps(bars, "2025-06-06", "2025-06-09", 1440)
    assert picked == bars


def test_interval_zero_keeps_every_in_window_bar():
    bars = _ts("2025-06-02 10:00", "2025-06-02 10:01", "2025-06-02 10:02")
    picked = select_simulation_timestamps(bars, "2025-06-02", "2025-06-02", 0)
    assert picked == bars


def test_empty_input_returns_empty():
    assert select_simulation_timestamps([], "2025-06-02", "2025-06-02", 30) == []
