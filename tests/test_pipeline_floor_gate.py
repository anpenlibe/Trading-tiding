"""Tests for the confidence floor gate in TradingPipeline._execute.

The floor is the code enforcement that makes the prompt's "only act above the floor"
rule real: a BUY/ADD below MIN_ACT_CONFIDENCE is skipped before risk/execution, while
exits and risk-reducing moves (SELL/TRIM/MOVE_STOP) are NEVER gated. Drives the real
PaperTrader + SimpleRiskManager + TradingPipeline — no LLM.
"""

from src.execution.executor import PaperTrader
from src.risk.manager import SimpleRiskManager
from src.pipeline import TradingPipeline
from src.platform.config import MIN_ACT_CONFIDENCE


def _pipe():
    t = PaperTrader(initial_capital=50_000.0)
    return t, TradingPipeline(brain=None, risk_manager=SimpleRiskManager(), executor=t)


def test_sub_floor_buy_is_skipped_and_opens_nothing():
    t, p = _pipe()
    r = p._execute("T", {"symbol": "T", "signal": "BUY", "confidence": MIN_ACT_CONFIDENCE - 0.1,
                         "entry_price": None}, 500.0, atr=5.0)
    assert r["status"] == "SKIPPED" and r["reason"] == "below_confidence_floor"
    assert not t.has_position("T")


def test_at_floor_buy_executes():
    t, p = _pipe()
    r = p._execute("T", {"symbol": "T", "signal": "BUY", "confidence": MIN_ACT_CONFIDENCE,
                         "entry_price": None}, 500.0, atr=5.0)
    assert r["status"] == "EXECUTED"
    assert t.has_position("T")


def test_missing_confidence_is_treated_as_sub_floor_for_buy():
    t, p = _pipe()
    r = p._execute("T", {"symbol": "T", "signal": "BUY", "entry_price": None}, 500.0, atr=5.0)
    assert r["status"] == "SKIPPED"
    assert not t.has_position("T")


def test_sell_is_never_floor_gated():
    t, p = _pipe()
    t.execute_simple_trade("T", "BUY", 500.0, 10, 490.0, 515.0)
    # A very low-confidence SELL must still close — exits are never blocked.
    r = p._execute("T", {"symbol": "T", "signal": "SELL", "confidence": 0.05}, 520.0, atr=5.0)
    assert r["status"] == "EXECUTED"
    assert not t.has_position("T")


def test_trim_and_move_stop_are_never_floor_gated():
    t, p = _pipe()
    t.execute_simple_trade("T", "BUY", 500.0, 20, 490.0, 560.0)
    trim = p._execute("T", {"symbol": "T", "signal": "TRIM", "trim_fraction": 0.25,
                           "confidence": 0.01}, 540.0, atr=5.0)
    assert trim["status"] == "EXECUTED"
    move = p._execute("T", {"symbol": "T", "signal": "MOVE_STOP", "new_stop": 495.0,
                           "confidence": 0.01}, 540.0, atr=5.0)
    assert move["status"] == "EXECUTED"
