"""Tests for the Indian-equity transaction-cost model (src/execution/costs.py).

compute_charges is a pure function over (turnover, side, product), so every charge
in the stack is exactly assertable. These pin the published NSE/Zerodha rate
schedule and the asymmetries that a flat commission can't express — the buy/sell
and delivery/intraday differences the whole affordability story depends on.
"""

from pytest import approx

from src.execution.costs import compute_charges


def test_delivery_buy_charges_breakdown():
    # turnover 10_000, delivery BUY:
    #   STT 0.1% = 10.00 | stamp 0.015% = 1.50 | exchange 0.00307% = 0.307
    #   SEBI ₹10/cr = 0.01 | GST 18% of (0+0.307+0.01) = 0.05706 | brokerage 0 | DP 0
    assert compute_charges(10_000, "BUY", "delivery") == approx(11.87, abs=0.005)


def test_delivery_sell_adds_dp_not_stamp():
    # delivery SELL: STT both sides (10.00), NO stamp (buy-only), DP charge 15.34 (sell-only)
    #   10.00 + 0.307 + 0.01 + 0.05706 + 15.34 = 25.71
    assert compute_charges(10_000, "SELL", "delivery") == approx(25.71, abs=0.005)


def test_delivery_stt_is_symmetric_but_stamp_and_dp_are_not():
    buy = compute_charges(10_000, "BUY", "delivery")
    sell = compute_charges(10_000, "SELL", "delivery")
    # The sell costs more by (DP 15.34 - stamp 1.50) = 13.84
    assert sell - buy == approx(13.84, abs=0.01)


def test_intraday_buy_has_brokerage_and_stamp_no_stt():
    # intraday BUY: brokerage min(20, 0.03%*10k=3.0)=3.0 | NO STT on buy | stamp 0.003% = 0.30
    #   3.0 + 0.307 + 0.01 + GST 0.18*(3.0+0.307+0.01)=0.59706 + 0.30 = 4.21
    assert compute_charges(10_000, "BUY", "intraday") == approx(4.21, abs=0.005)


def test_intraday_sell_has_stt_no_stamp():
    # intraday SELL: brokerage 3.0 | STT 0.025% = 2.50 | NO stamp | NO DP
    #   3.0 + 2.50 + 0.307 + 0.01 + 0.59706 = 6.41
    assert compute_charges(10_000, "SELL", "intraday") == approx(6.41, abs=0.005)


def test_intraday_brokerage_is_capped_at_20():
    # 0.03% of 1_000_000 = 300, but brokerage caps at ₹20 per leg.
    #   20 + exchange 30.7 + SEBI 1.0 + GST 0.18*(20+30.7+1.0)=9.306 + stamp 30.0 (buy) = 91.01
    assert compute_charges(1_000_000, "BUY", "intraday") == approx(91.01, abs=0.02)


def test_side_is_case_insensitive():
    assert compute_charges(10_000, "buy", "delivery") == compute_charges(10_000, "BUY", "delivery")
    assert compute_charges(10_000, "sell", "intraday") == compute_charges(10_000, "SELL", "intraday")


def test_zero_or_negative_turnover_is_free():
    assert compute_charges(0, "BUY", "delivery") == 0.0
    assert compute_charges(-100, "SELL", "delivery") == 0.0


def test_charges_scale_with_turnover():
    # Delivery has no fixed/capped component, so charges are ~linear in turnover.
    # Not EXACTLY 2x: compute_charges rounds to paise, so 11.87 (10k) vs 23.75 (20k)
    # differ from 2x by one paise of rounding. Allow that, but pin linearity tightly.
    one = compute_charges(10_000, "BUY", "delivery")
    two = compute_charges(20_000, "BUY", "delivery")
    assert two == approx(2 * one, abs=0.02)
