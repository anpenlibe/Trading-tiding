"""Regression test for the performance monitoring decorator.

Pins the bug where performance_tracker timed a call and logged it but never
called record_metric — so PerformanceMonitor.metrics stayed empty and the
dashboard's "Operation Performance" section was permanently blank.
"""

import pytest

from src.monitoring.performance import performance_tracker, get_monitor


def test_performance_tracker_records_metric():
    @performance_tracker('unit_test_ok')
    def add(a, b):
        return a + b

    assert add(2, 3) == 5

    measurements = get_monitor().metrics.get('unit_test_ok')
    assert measurements, "decorator must record a metric on the global monitor"
    assert measurements[-1]['success'] is True
    assert measurements[-1]['duration'] >= 0


def test_performance_tracker_records_failure_and_reraises():
    @performance_tracker('unit_test_fail')
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        boom()

    measurements = get_monitor().metrics.get('unit_test_fail')
    assert measurements, "a failing call must still be recorded"
    assert measurements[-1]['success'] is False
