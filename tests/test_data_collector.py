"""Regression tests for DataCollector resilience helpers.

Pins the fix where a data source that returns None on failure (Zerodha with an
expired token, rate-limited Yahoo) never tripped its circuit breaker, so it got
re-probed for every symbol. _fetch_or_raise converts an empty result into an
exception the breaker counts.
"""

import time

import pytest

from src.data_collector import DataCollector
from src.utils.retry import CircuitBreaker


class _DeadAPI:
    def fetch_ohlc(self, symbol):
        return None  # always fails, returns None (no raise)


class _LiveAPI:
    def fetch_ohlc(self, symbol):
        return {"symbol": symbol}  # truthy -> success


def test_fetch_or_raise_raises_on_empty():
    with pytest.raises(RuntimeError):
        DataCollector._fetch_or_raise(_DeadAPI(), "TCS")


def test_fetch_or_raise_passes_through_data():
    assert DataCollector._fetch_or_raise(_LiveAPI(), "TCS") == {"symbol": "TCS"}


def test_breaker_opens_then_fast_fails_on_dead_source():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=300)
    for _ in range(3):
        with pytest.raises(Exception):
            cb.call(DataCollector._fetch_or_raise, _DeadAPI(), "TCS")
    assert cb.state == "OPEN"

    # Once open, calls short-circuit fast instead of re-probing the dead source.
    start = time.time()
    with pytest.raises(Exception) as exc:
        cb.call(DataCollector._fetch_or_raise, _DeadAPI(), "TCS")
    assert "OPEN" in str(exc.value)
    assert (time.time() - start) < 0.1


def test_healthy_source_never_trips():
    cb = CircuitBreaker(failure_threshold=3)
    for _ in range(5):
        cb.call(DataCollector._fetch_or_raise, _LiveAPI(), "TCS")
    assert cb.state == "CLOSED"


def test_paper_collector_has_mock_fallback_and_breakers():
    """_init_apis must add MockAPI as a guaranteed last resort in paper mode and
    register a circuit breaker per source."""
    dc = DataCollector()
    try:
        names = [a.get_name() for a in dc.apis]
        assert "mock" in names  # guaranteed paper-mode fallback
        # Every wired source has a breaker keyed by its class name.
        for api in dc.apis:
            assert api.__class__.__name__ in dc.api_circuit_breakers
    finally:
        dc.close()


def test_removed_dead_methods_stay_removed():
    """collect_all_symbols, fetch_with_fallback, and the legacy save_* wrappers
    were dead (zero callers) and should not return."""
    for name in ("collect_all_symbols", "fetch_with_fallback",
                 "save_market_data", "save_indicators"):
        assert not hasattr(DataCollector, name), f"{name} was dead and should stay removed"
