"""Regression tests for the historical backtester's bar-selection logic.

Pins the fixes for two correctness/robustness bugs in apps/backtest.py:

1. The old sampler used exact modulo alignment (`time_diff % interval == 0`)
   against wall-clock minutes from the first bar. When an N-days-later slot fell
   on a weekend/holiday it was SILENTLY dropped, and the sampler only re-synced
   at exact multiples of the interval — so a 3-day step could quietly become a
   6-day step. The cumulative rule ("keep a bar once >= interval minutes since
   the last kept bar") is robust across gaps.

2. The intraday `hour >= 10` filter wiped out pure-daily snapshots (one midnight
   bar per day) → "0 time points" with no error. Selection now falls back to
   daily bars when no intraday bars exist in the window.

These cover the pure, importable helpers; the non-interactive CLI path is
exercised manually (see the explicit-date invocation in apps/backtest.py).
"""

import pandas as pd

from apps.backtest import select_simulation_timestamps, format_interval

ONE_DAY = 1440  # minutes


def _bars(dates, hours):
    """Build a flat list of pd.Timestamps for the given dates x hours."""
    return [pd.Timestamp(f"{d} {h:02d}:00:00") for d in dates for h in hours]


def test_subday_interval_keeps_every_hourly_bar():
    """The documented common case (30-min interval on hourly bars) is preserved:
    every hourly bar is kept, matching the prior verified behavior."""
    ts = _bars(["2025-11-10", "2025-11-11"], range(10, 16))
    out = select_simulation_timestamps(ts, "2025-11-10", "2025-11-11", 30)
    assert out == sorted(ts)


def test_three_day_interval_picks_start_and_plus_three_days():
    """A week sampled at a 3-day interval yields the start day and exactly the
    bar 3 days later (both trading days), not the whole week."""
    dates = ["2025-11-10", "2025-11-11", "2025-11-12",
             "2025-11-13", "2025-11-14", "2025-11-17"]
    ts = _bars(dates, [10])
    out = select_simulation_timestamps(ts, "2025-11-10", "2025-11-16", 3 * ONE_DAY)
    assert [t.strftime("%Y-%m-%d") for t in out] == ["2025-11-10", "2025-11-13"]


def test_interval_is_robust_across_weekend_gap():
    """Regression: when the +3-day slot lands on a weekend (no bar), the next
    available trading bar is still kept (cumulative spacing) rather than being
    silently dropped the way exact modulo alignment did."""
    dates = ["2025-11-13", "2025-11-14", "2025-11-17", "2025-11-18", "2025-11-19"]
    ts = _bars(dates, [10])
    out = select_simulation_timestamps(ts, "2025-11-13", "2025-11-20", 3 * ONE_DAY)
    picked = [t.strftime("%Y-%m-%d") for t in out]
    assert picked[0] == "2025-11-13"
    # Mon 11-17 is the first bar >= 3 days after Thu 11-13 (Sun 11-16 has none);
    # it must be kept, not dropped.
    assert "2025-11-17" in picked


def test_falls_back_to_daily_bars_when_no_intraday():
    """Pure-daily snapshot (only midnight bars) must still simulate instead of
    silently producing zero time points."""
    ts = _bars(["2025-11-10", "2025-11-11", "2025-11-12"], [0])
    out = select_simulation_timestamps(ts, "2025-11-10", "2025-11-12", ONE_DAY)
    assert len(out) == 3


def test_out_of_window_bars_excluded():
    """Bars outside [start, end] are never selected (context days included for
    indicators must not become decision points)."""
    ts = _bars(["2025-11-07", "2025-11-10", "2025-11-11", "2025-11-20"], [10])
    out = select_simulation_timestamps(ts, "2025-11-10", "2025-11-11", 30)
    dates = {t.strftime("%Y-%m-%d") for t in out}
    assert dates == {"2025-11-10", "2025-11-11"}


def test_format_interval_renders_human_units():
    assert format_interval(3 * ONE_DAY) == "3 days"
    assert format_interval(ONE_DAY) == "1 day"
    assert format_interval(60) == "1 hour"
    assert format_interval(120) == "2 hours"
    assert format_interval(30) == "30 minutes"
