"""Tests for the portfolio / alert-review response parser (no LLM — synthetic JSON).

The parser is the safety-critical seam: a parse miss degrades to HOLD silently, so these
assert the verb vocabulary and reasoning/thesis/verb-param fields survive parsing, unknown
verbs degrade to HOLD, and a missing symbol gets the uniform default shape.
"""

import json
import pandas as pd
import pytest

from src.decision.prompts import PromptBuilder


def _df(price=500.0):
    return pd.DataFrame({'open': [price], 'high': [price], 'low': [price],
                         'close': [price], 'volume': [1000], 'symbol': ['T']})


def test_parse_portfolio_reads_new_fields_and_verbs():
    pdata = {'T': _df(500.0)}
    raw = json.dumps({
        "market_analysis": "neutral regime",
        "decisions": {
            "T": {
                "reasoning": "thesis weakening, lock in",
                "signal": "MOVE_STOP",
                "confidence": 0.8,
                "thesis": "momentum fading",
                "thesis_status": "weakening",
                "new_stop": 495.0,
                "trim_fraction": None,
            }
        }
    })
    out = PromptBuilder.parse_portfolio_response(raw, pdata, context={'current_positions': ['T']})
    d = out['decisions']['T']
    assert d['signal'] == 'MOVE_STOP'
    assert d['thesis_status'] == 'weakening'
    assert d['new_stop'] == pytest.approx(495.0)


def test_parse_portfolio_unknown_verb_degrades_to_hold():
    pdata = {'T': _df(500.0)}
    raw = json.dumps({"decisions": {"T": {"signal": "YOLO", "confidence": 0.9}}})
    out = PromptBuilder.parse_portfolio_response(raw, pdata, context={})
    assert out['decisions']['T']['signal'] == 'HOLD'


def test_parse_portfolio_missing_symbol_gets_uniform_default_shape():
    pdata = {'T': _df(500.0), 'U': _df(300.0)}
    raw = json.dumps({"market_analysis": "x", "decisions": {
        "T": {"reasoning": "r", "signal": "HOLD", "confidence": 0.5}}})
    out = PromptBuilder.parse_portfolio_response(raw, pdata, context={})
    # U absent from response -> safe HOLD default carrying the new keys (uniform shape).
    u = out['decisions']['U']
    assert u['signal'] == 'HOLD'
    assert 'thesis_status' in u and 'trim_fraction' in u and 'new_stop' in u
