"""Tests for Phase 5: mean-reversion surfacing, the regime entry-gate, and the
consolidated alert review. Synthetic — no LLM (a FakeBrain returns decisions directly).
"""

import pandas as pd

from src.execution.executor import PaperTrader
from src.risk.manager import SimpleRiskManager
from src.pipeline import TradingPipeline, _entries_allowed
from src.alerts.rules import OversoldPullbackRule, SupportPullbackRule


def _df(p=500.0):
    return pd.DataFrame({'open': [p] * 5, 'high': [p] * 5, 'low': [p] * 5,
                         'close': [p] * 5, 'volume': [1000] * 5, 'symbol': ['T'] * 5})


def _weak():   # breadth ~0% above SMA50 -> entries blocked
    return {s: {'rsi_14': 40, 'price_vs_sma50_pct': -2.0} for s in 'ABCDE'}


def _strong():  # breadth 100% above SMA50 -> entries allowed
    return {s: {'rsi_14': 60, 'price_vs_sma50_pct': 3.0} for s in 'ABCDE'}


# ----- surfacing predicates (dips in strong names, not momentum) -------------------

def test_oversold_pullback_fires_only_in_uptrend():
    r = OversoldPullbackRule('T')
    assert r.check({'symbol': 'T', 'close': 105, 'indicators': {'rsi_14': 30, 'sma_50': 100}}) is True
    # oversold but in a DOWNtrend (below SMA50) — a falling knife, not surfaced.
    assert r.check({'symbol': 'T', 'close': 95, 'indicators': {'rsi_14': 30, 'sma_50': 100}}) is False
    # above SMA50 but not oversold — nothing to consider.
    assert r.check({'symbol': 'T', 'close': 105, 'indicators': {'rsi_14': 60, 'sma_50': 100}}) is False


def test_support_pullback_band():
    r = SupportPullbackRule('T')  # 1% band
    assert r.check({'symbol': 'T', 'close': 100.5, 'indicators': {'sma_20': 100, 'sma_50': 80}}) is True
    assert r.check({'symbol': 'T', 'close': 110, 'indicators': {'sma_20': 100, 'sma_50': 80}}) is False  # extended
    assert r.check({'symbol': 'T', 'close': 98, 'indicators': {'sma_20': 100, 'sma_50': 80}}) is False   # below MA


# ----- regime gate ----------------------------------------------------------------

def test_entries_allowed_tracks_breadth():
    assert _entries_allowed(_weak()) is False
    assert _entries_allowed(_strong()) is True
    assert _entries_allowed({}) is True  # no breadth data -> don't silently block


class _FakeBrain:
    def __init__(self, decisions):
        self._d = decisions

    def analyze_portfolio_with_intelligent_fallback(self, pdata, pind, ctx):
        return {'market_analysis': '', 'decisions': self._d}

    def analyze_alert_review(self, pdata, pind, owned, cands, ctx):
        return {'market_analysis': '', 'decisions': self._d}


def _pipe(decisions):
    t = PaperTrader(initial_capital=50_000.0)
    return t, TradingPipeline(_FakeBrain(decisions), SimpleRiskManager(), t)


def test_regime_gate_blocks_buy_in_weak_breadth():
    t, p = _pipe({'T': {'signal': 'BUY', 'confidence': 0.8, 'entry_price': None, 'reasoning': 'x'}})
    pind = {**_weak(), 'T': {'atr_14': 5, 'price_vs_sma50_pct': -1.0}}
    p.run_decisions({'T': _df()}, pind, {'T': 500.0}, {})
    assert not t.has_position('T')  # blocked by weak regime (confidence 0.8 clears the floor)


def test_regime_gate_allows_buy_in_strong_breadth():
    t, p = _pipe({'T': {'signal': 'BUY', 'confidence': 0.8, 'entry_price': None, 'reasoning': 'x'}})
    pind = {**_strong(), 'T': {'atr_14': 5, 'price_vs_sma50_pct': 3.0}}
    p.run_decisions({'T': _df()}, pind, {'T': 500.0}, {})
    assert t.has_position('T')


def test_regime_gate_never_blocks_exits():
    t, p = _pipe({'T': {'signal': 'SELL', 'confidence': 0.1, 'reasoning': 'exit'}})
    t.execute_simple_trade('T', 'BUY', 500.0, 10, 490.0, 520.0)
    pind = {**_weak(), 'T': {'atr_14': 5}}
    p.run_decisions({'T': _df()}, pind, {'T': 520.0}, {})
    assert not t.has_position('T')  # SELL executes despite weak regime


# ----- consolidated alert review --------------------------------------------------

def test_alert_review_manages_holding_and_gates_candidate():
    decisions = {
        'OWN': {'signal': 'TRIM', 'trim_fraction': 0.25, 'confidence': 0.7, 'reasoning': 'weakening'},
        'CAND': {'signal': 'BUY', 'confidence': 0.8, 'entry_price': None, 'reasoning': 'dip'},
    }
    t, p = _pipe(decisions)
    t.execute_simple_trade('OWN', 'BUY', 500.0, 20, 490.0, 560.0)
    out = p.run_alert_review(
        {'OWN': _df(500), 'CAND': _df(300)},
        {'OWN': {'atr_14': 5}, 'CAND': {'atr_14': 3}},
        {'OWN': 540.0, 'CAND': 300.0}, {}, ['OWN'], ['CAND'],
        regime_indicators=_weak(),  # weak tape
    )
    # Manage verb on the holding runs (never gated); candidate BUY blocked by weak regime.
    assert t.book.open_positions['OWN'].quantity == 15   # trimmed 25% of 20
    assert not t.has_position('CAND')
