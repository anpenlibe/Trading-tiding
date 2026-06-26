"""Tests for SimpleRiskManager (src/risk/manager.py).

Covers the two things most likely to break silently:
  - ATR-scaled stop/target geometry and the 1.5 reward:risk that ATR sizing lands
    on EXACTLY — the gate rejects ``< 1.5``, so a regression there kills every ATR
    trade. This is the tripwire test.
  - validate_trade's (is_valid, reason, risk_params) contract — the 3-tuple the
    pipeline reuses so it executes precisely what was validated.
"""

from pytest import approx

from src.risk.manager import SimpleRiskManager, RiskParameters, conviction_risk_percent
from src.platform.config import (
    MAX_POSITION_SIZE, MAX_RISK_PER_TRADE, MIN_ACT_CONFIDENCE, CONVICTION_RISK_FLOOR_FRAC,
)


def _rm():
    return SimpleRiskManager()


# ----- calculate_risk_parameters: ATR geometry -----------------------------------

def test_atr_sets_stop_and_target_around_raw_entry():
    rp = _rm().calculate_risk_parameters(
        symbol="T", signal_type="BUY", entry_price=500.0, capital=50_000.0, atr=5.0)
    # stop = entry - 2*ATR = 490 ; target = entry + 3*ATR = 515
    assert rp.stop_loss == approx(490.0)
    assert rp.target == approx(515.0)


def test_atr_reward_risk_is_exactly_1_5_and_clears_the_gate():
    # 3*ATR : 2*ATR = 1.5 — computed against the RAW entry (not slippage-adjusted),
    # which is the whole reason ATR trades clear the `>= 1.5` validation gate.
    rp = _rm().calculate_risk_parameters(
        symbol="T", signal_type="BUY", entry_price=500.0, capital=50_000.0, atr=5.0)
    assert rp.risk_reward_ratio == approx(1.5)
    assert rp.risk_reward_ratio >= 1.5  # the gate is `< 1.5 -> reject`


def test_entry_price_is_slippage_adjusted_for_a_buy():
    rm = _rm()  # default PAPER_TRADE_SLIPPAGE = 0.0005
    rp = rm.calculate_risk_parameters(
        symbol="T", signal_type="BUY", entry_price=500.0, capital=50_000.0, atr=5.0)
    assert rp.entry_price == approx(500.0 * (1 + rm.slippage))


def test_fixed_percent_fallback_when_no_atr():
    rp = _rm().calculate_risk_parameters(
        symbol="T", signal_type="BUY", entry_price=500.0, capital=50_000.0, atr=None)
    # fixed: stop -1.5% = 492.5, target +3% = 515 -> RR = 15/7.5 = 2.0
    assert rp.stop_loss == approx(492.5)
    assert rp.target == approx(515.0)
    assert rp.risk_reward_ratio == approx(2.0)


# ----- validate_trade: the 3-tuple contract --------------------------------------

def test_valid_buy_returns_riskparams():
    is_valid, reason, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "BUY", "entry_price": 500.0, "available_capital": 50_000.0},
        current_positions={}, atr=5.0)
    assert is_valid is True
    assert reason is None
    assert isinstance(rp, RiskParameters)
    assert rp.position_size > 0


def test_sell_short_circuits_with_no_params():
    # A SELL is a full close; it needs no sizing, so risk_params is None.
    assert _rm().validate_trade(
        {"symbol": "T", "signal": "SELL", "entry_price": 500.0}, {}, atr=5.0) == (True, None, None)


def test_reject_when_single_share_exceeds_position_cap():
    is_valid, reason, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "BUY", "entry_price": 999_999.0, "available_capital": 50_000.0},
        current_positions={}, atr=5.0)
    assert is_valid is False
    assert rp is None
    assert "exceeds max position" in reason


def test_reject_when_already_holding_the_symbol():
    is_valid, reason, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "BUY", "entry_price": 500.0, "available_capital": 50_000.0},
        current_positions={"T": {"quantity": 10}}, atr=5.0)
    assert is_valid is False
    assert rp is None
    assert "Already have open position" in reason


def test_reject_when_no_entry_price():
    is_valid, reason, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "BUY", "available_capital": 50_000.0}, {}, atr=5.0)
    assert is_valid is False
    assert rp is None


def test_position_value_respects_capital_cap():
    # Sized position value must never exceed MAX_POSITION_SIZE of capital.
    _, _, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "BUY", "entry_price": 500.0, "available_capital": 50_000.0},
        current_positions={}, atr=5.0)
    assert rp.position_value <= 50_000.0 * MAX_POSITION_SIZE + 1e-6


# ----- validate_trade: new verb routing (ADD / TRIM / MOVE_STOP) ------------------

def test_trim_and_move_stop_require_a_held_position():
    rm = _rm()
    held = {"T": {"quantity": 10, "entry_price": 500.0}}
    assert rm.validate_trade({"symbol": "T", "signal": "TRIM"}, {}, atr=5.0)[0] is False
    assert rm.validate_trade({"symbol": "T", "signal": "TRIM"}, held, atr=5.0) == (True, None, None)
    assert rm.validate_trade({"symbol": "T", "signal": "MOVE_STOP"}, {}, atr=5.0)[0] is False
    assert rm.validate_trade({"symbol": "T", "signal": "MOVE_STOP"}, held, atr=5.0) == (True, None, None)


def test_add_sizes_the_increment_when_aggregate_room_exists():
    # Held 4 @ 500 = 2000; cap 20% of 50k = 10000 -> ample room -> ADD is sized.
    ok, _, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "ADD", "entry_price": 500.0, "available_capital": 50_000.0},
        current_positions={"T": {"quantity": 4, "entry_price": 500.0}}, atr=5.0)
    assert ok is True
    assert rp is not None and rp.position_size >= 1


def test_add_rejected_when_aggregate_at_cap():
    # Held 20 @ 500 = 10000 == the 20% cap -> no room -> reject.
    ok, reason, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "ADD", "entry_price": 500.0, "available_capital": 50_000.0},
        current_positions={"T": {"quantity": 20, "entry_price": 500.0}}, atr=5.0)
    assert ok is False and rp is None and "cap" in reason


def test_add_rejected_when_increment_below_minimum():
    # Held 18 @ 500 = 9000; only ~1000 room -> increment below MIN_TRADE_VALUE -> reject.
    ok, _, rp = _rm().validate_trade(
        {"symbol": "T", "signal": "ADD", "entry_price": 500.0, "available_capital": 50_000.0},
        current_positions={"T": {"quantity": 18, "entry_price": 500.0}}, atr=5.0)
    assert ok is False and rp is None


# ----- conviction sizing: confidence -> risk_per_trade ----------------------------

def test_conviction_risk_percent_endpoints():
    # Floor confidence -> floor fraction of the cap; full confidence -> full cap.
    assert conviction_risk_percent(MIN_ACT_CONFIDENCE) == approx(MAX_RISK_PER_TRADE * CONVICTION_RISK_FLOOR_FRAC)
    assert conviction_risk_percent(1.0) == approx(MAX_RISK_PER_TRADE)
    # Midpoint (0.8 with floor 0.6) is halfway up the band.
    mid = MAX_RISK_PER_TRADE * (CONVICTION_RISK_FLOOR_FRAC + (1 - CONVICTION_RISK_FLOOR_FRAC) * 0.5)
    assert conviction_risk_percent(0.8) == approx(mid)


def test_conviction_risk_percent_clamps_both_ends():
    # Below the floor clamps UP to floor-frac (never below); above 1.0 clamps to cap.
    assert conviction_risk_percent(0.0) == approx(MAX_RISK_PER_TRADE * CONVICTION_RISK_FLOOR_FRAC)
    assert conviction_risk_percent(2.0) == approx(MAX_RISK_PER_TRADE)
    # Never exceeds the hard cap.
    assert conviction_risk_percent(0.95) <= MAX_RISK_PER_TRADE


def test_higher_confidence_sizes_a_larger_position():
    # Wide ATR (=30 -> 60 stop distance) so RISK, not the 20% capital cap, binds the
    # size; otherwise both confidences clip to the same max-position-value share count
    # and the conviction difference is invisible. Here a higher risk_per_trade yields
    # strictly more shares.
    rm = _rm()
    _, _, lo = rm.validate_trade(
        {"symbol": "T", "signal": "BUY", "entry_price": 500.0, "available_capital": 50_000.0, "confidence": 0.6},
        current_positions={}, atr=30.0)
    _, _, hi = rm.validate_trade(
        {"symbol": "T", "signal": "BUY", "entry_price": 500.0, "available_capital": 50_000.0, "confidence": 1.0},
        current_positions={}, atr=30.0)
    assert hi.position_size > lo.position_size


def test_add_increment_scales_with_confidence():
    rm = _rm()
    held = {"T": {"quantity": 4, "entry_price": 500.0}}  # room to add
    _, _, lo = rm.validate_trade(
        {"symbol": "T", "signal": "ADD", "entry_price": 500.0, "available_capital": 50_000.0, "confidence": 0.6},
        current_positions=held, atr=5.0)
    _, _, hi = rm.validate_trade(
        {"symbol": "T", "signal": "ADD", "entry_price": 500.0, "available_capital": 50_000.0, "confidence": 1.0},
        current_positions=held, atr=5.0)
    assert hi.position_size >= lo.position_size
