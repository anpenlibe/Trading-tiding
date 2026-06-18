"""Regression tests for the AI rule-based fallback path.

Pins the two-part bug: the coordinator returned an unparseable placeholder
string on exhaustion (so AIBrain's RSI fallbacks were unreachable), and
_fallback_portfolio_analysis returned a bare {symbol: decision} instead of the
wrapped {'decisions': ...} shape every caller expects.

These tests stub the coordinator so no network/API calls happen.
"""

import pandas as pd
import pytest


def _ohlc(n=25, close=100.0):
    return pd.DataFrame({
        'symbol': ['TCS'] * n,
        'open': [close] * n, 'high': [close + 1] * n,
        'low': [close - 1] * n, 'close': [close] * n,
        'volume': [10000] * n,
    })


@pytest.fixture
def exhausted_brain():
    """AIBrain whose coordinator always fails (simulates all providers down)."""
    from src.core.ai_brain import AIBrain
    brain = AIBrain()

    def _boom(*args, **kwargs):
        raise Exception("all providers exhausted")

    brain.coordinator.call_with_fallback = _boom
    return brain


def test_coordinator_raises_on_exhaustion(monkeypatch):
    """call_with_fallback must RAISE (not return a junk string) so AIBrain can
    apply its schema-aware fallback.

    Note: the constructor does `fallback_chain or default`, so an empty list is
    replaced by the real chain — we instead force the single provider to fail,
    with no network calls.
    """
    from src.ai.provider_coordinator import ProviderCoordinator, ProviderConfig
    from src.exceptions import AIAnalysisError

    coord = ProviderCoordinator(
        fallback_chain=[ProviderConfig("groq", "fake-model", 100, "fake-key")]
    )

    def _always_fail(_config):
        raise RuntimeError("provider down")

    monkeypatch.setattr(coord, "_get_or_create_client", _always_fail)

    with pytest.raises(AIAnalysisError):
        coord.call_with_fallback("any prompt")


def test_single_symbol_fallback_uses_rsi(exhausted_brain):
    """Oversold RSI should yield a BUY from the rule-based fallback, not a
    parse-error HOLD."""
    decision = exhausted_brain.analyze(_ohlc(), {'rsi_14': 25})
    assert decision['signal'] == 'BUY'
    assert 0 < decision['confidence'] <= 1


def test_open_circuit_breaker_still_uses_rsi_fallback(exhausted_brain):
    """With the AI circuit breaker already open, analyze() must STILL run the
    rule-based RSI fallback (it makes no API calls) — not return a blind HOLD.

    Pins the degraded-run bug: once 5 consecutive provider failures tripped the
    breaker, every remaining symbol got HOLD 0.0, silently disabling the RSI
    fallback for the rest of the cycle.
    """
    exhausted_brain.consecutive_failures = exhausted_brain.max_consecutive_failures
    decision = exhausted_brain.analyze(_ohlc(), {'rsi_14': 25})  # oversold
    assert decision['signal'] == 'BUY'
    assert 0 < decision['confidence'] <= 1


def test_portfolio_fallback_has_wrapped_shape(exhausted_brain):
    """Fallback portfolio result must be {'decisions': {...}}, populated."""
    result = exhausted_brain._analyze_portfolio_batch(
        {'TCS': _ohlc()}, {'TCS': {'rsi_14': 25}}, {},
    )
    assert isinstance(result, dict)
    assert 'decisions' in result
    assert 'TCS' in result['decisions']
    assert result['decisions']['TCS']['signal'] in ('BUY', 'SELL', 'HOLD')
