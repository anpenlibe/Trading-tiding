"""Tests for Phase 3 memory plumbing: per-position thesis, watchlist intent, decision trail.

All synthetic — no LLM. Asserts the DATA is stored and threaded; rendering into prompts
is Phase 4. The thesis seeds from the decision's `reasoning` (the field the model emits
today) so this works before the prompt rewrite.
"""

from src.execution.executor import PaperTrader
from src.alerts.manager import AlertManager
from src.decision.engine import AIBrain


# ----- per-position thesis (seeded from reasoning, evolves on ADD) -----------------

def test_buy_seeds_entry_thesis_from_reasoning():
    t = PaperTrader(initial_capital=50_000.0)
    t.execute_trade({'symbol': 'T', 'signal': 'BUY', 'position_size': 10,
                     'confidence': 0.8, 'reasoning': 'SMA50 breakout on 2x volume'}, 500.0)
    pos = t.get_positions()['T']
    assert pos['entry_thesis'] == 'SMA50 breakout on 2x volume'
    assert pos['thesis'] == 'SMA50 breakout on 2x volume'
    assert pos['thesis_status'] == 'intact'


def test_add_evolves_thesis_but_entry_thesis_is_immutable():
    t = PaperTrader(initial_capital=50_000.0)
    t.execute_trade({'symbol': 'T', 'signal': 'BUY', 'position_size': 2,
                     'confidence': 0.8, 'reasoning': 'initial breakout'}, 500.0)
    t.execute_trade({'symbol': 'T', 'signal': 'ADD', 'position_size': 3,
                     'reasoning': 'breakout confirmed, adding', 'thesis_status': 'intact'}, 510.0)
    pos = t.get_positions()['T']
    assert pos['entry_thesis'] == 'initial breakout'        # immutable
    assert pos['thesis'] == 'breakout confirmed, adding'    # evolved


def test_update_thesis_status_keeps_prose_when_only_status_changes():
    t = PaperTrader(initial_capital=50_000.0)
    t.execute_trade({'symbol': 'T', 'signal': 'BUY', 'position_size': 10,
                     'confidence': 0.8, 'reasoning': 'breakout'}, 500.0)
    t.book.update_thesis('T', status='weakening')  # status only
    pos = t.get_positions()['T']
    assert pos['thesis'] == 'breakout'          # prose untouched
    assert pos['thesis_status'] == 'weakening'


# ----- watchlist intent (repairs the dead context['watchlist'] seam) --------------

def test_watchlist_intent_captured_and_exposed():
    am = AlertManager(['TCS', 'INFY'])
    am.update_from_general({
        'TCS': {'signal': 'HOLD', 'watchlist': True, 'watchlist_reason': 'want pullback ~3150',
                'alert_conditions': {'price_below': 3150}},
        'INFY': {'signal': 'HOLD', 'watchlist': False},
    }, positions={})
    assert am.get_watchlist_symbols() == ['TCS']
    intent = am.get_watchlist_intent()
    assert intent['TCS']['reason'] == 'want pullback ~3150'
    assert intent['TCS']['conditions'] == {'price_below': 3150}


def test_watchlist_intent_round_trips_through_seed():
    am = AlertManager(['TCS'])
    am.update_from_general({'TCS': {'signal': 'HOLD', 'watchlist': True,
                                    'watchlist_reason': 'oversold soon',
                                    'alert_conditions': {'rsi_below': 30}}}, positions={})
    saved = am.get_watchlist_intent()
    # Fresh manager (simulating a restart) restores the same standing watchlist.
    am2 = AlertManager(['TCS'])
    assert am2.get_watchlist_symbols() == []   # starts empty
    am2.seed_watchlist_intent(saved, positions={})
    assert am2.get_watchlist_symbols() == ['TCS']
    assert am2.get_watchlist_intent()['TCS']['reason'] == 'oversold soon'


# ----- decision trail -------------------------------------------------------------

def test_recent_decisions_by_symbol_caps_and_orders():
    brain = AIBrain(mode='backtest')
    # Seed history directly (avoids needing the LLM).
    import pandas as pd
    for i, sig in enumerate(['HOLD', 'BUY', 'HOLD', 'SELL']):
        brain.decision_history.append({
            'timestamp': pd.Timestamp.now(), 'symbol': 'T', 'signal': sig,
            'confidence': 0.5 + i * 0.1, 'reasoning': f'r{i}', 'price': 500, 'rsi': 50, 'macd': 0,
        })
    trail = brain.recent_decisions_by_symbol(n=2)
    assert len(trail['T']) == 2
    # Most-recent-first: the last appended (SELL) leads.
    assert trail['T'][0]['signal'] == 'SELL'
    assert trail['T'][1]['signal'] == 'HOLD'
