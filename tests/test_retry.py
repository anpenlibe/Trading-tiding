"""Regression tests for retry_with_backoff and CircuitBreaker.

retry_with_backoff decorates three data_collector methods but had zero tests;
this pins its core contract. Small delays keep the suite fast.
"""

import pytest

from src.utils.retry import retry_with_backoff, CircuitBreaker

FAST = dict(initial_delay=0.001, max_delay=0.001)


def _raise(exc=None):
    raise exc or RuntimeError("boom")


def test_returns_immediately_on_success():
    calls = []

    @retry_with_backoff(max_retries=3, **FAST)
    def ok():
        calls.append(1)
        return "done"

    assert ok() == "done"
    assert len(calls) == 1  # no retries on first-try success


def test_retries_then_raises():
    calls = []

    @retry_with_backoff(max_retries=2, **FAST)
    def boom():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        boom()
    assert len(calls) == 3  # 1 initial attempt + 2 retries


def test_eventually_succeeds_after_failures():
    calls = []

    @retry_with_backoff(max_retries=5, **FAST)
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("transient")
        return "recovered"

    assert flaky() == "recovered"
    assert len(calls) == 3


def test_only_listed_exceptions_are_retried():
    calls = []

    @retry_with_backoff(max_retries=3, exceptions=(ValueError,), **FAST)
    def wrong_error():
        calls.append(1)
        raise KeyError("unlisted")

    with pytest.raises(KeyError):
        wrong_error()
    assert len(calls) == 1  # an unlisted exception is not retried


def test_on_retry_callback_fires_per_retry():
    seen = []

    @retry_with_backoff(max_retries=2, on_retry=lambda attempt, exc: seen.append(attempt), **FAST)
    def boom():
        raise ValueError("x")

    with pytest.raises(ValueError):
        boom()
    assert seen == [1, 2]  # fires on each retry, not on the final raise


def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(_raise)
    assert cb.state == "OPEN"
    # Once OPEN the breaker rejects without invoking the function.
    with pytest.raises(Exception):
        cb.call(_raise)


def test_circuit_breaker_recovers_to_closed():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
    with pytest.raises(RuntimeError):
        cb.call(_raise)
    assert cb.state == "OPEN"
    cb.last_failure_time = 0  # pretend the recovery timeout has long elapsed
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state == "CLOSED"
    assert cb.failure_count == 0
