"""Regression tests for the top-level TradingOrchestrator (apps/trader.py).

Pins the orchestration-pass changes:
- ClaudeTrader was renamed to TradingOrchestrator (the class is the orchestrator,
  not a Claude-specific executor).
- Three pre-_*_safely duplicate methods were dead and removed.
- _generate_signal_safely now stamps the symbol onto the decision, so a valid
  BUY isn't rejected downstream as "Signal missing 'symbol'".

The orchestrator's real __init__ builds the whole (network-touching) stack, so
the signal test constructs the instance via object.__new__ and injects fakes for
just the two collaborators _generate_signal_safely uses.
"""

import pandas as pd

import apps.trader as trader


def test_orchestrator_renamed():
    assert hasattr(trader, 'TradingOrchestrator')
    assert not hasattr(trader, 'ClaudeTrader'), "old name must be gone after the rename"


def test_dead_duplicate_methods_removed():
    for dead in ('_get_claude_decision', '_get_market_data_and_indicators', '_execute_signal'):
        assert not hasattr(trader.TradingOrchestrator, dead), f"{dead} was dead; keep it removed"


class _FakeCollector:
    def get_recent_data(self, symbol, *args, **kwargs):
        return pd.DataFrame({'close': [100.0]})


class _FakeBrain:
    def analyze(self, df, indicators):
        return {'signal': 'BUY', 'confidence': 0.8, 'reasoning': 'test'}


def test_generate_signal_stamps_symbol():
    """The decision returned by analyze() has no 'symbol' key; the orchestrator
    must stamp it so execute_trade (which keys off signal['symbol']) accepts it."""
    orch = object.__new__(trader.TradingOrchestrator)  # skip heavy __init__
    orch.data_collector = _FakeCollector()
    orch.ai_brain = _FakeBrain()

    signal = orch._generate_signal_safely('TCS')
    assert signal is not None
    assert signal['symbol'] == 'TCS'
