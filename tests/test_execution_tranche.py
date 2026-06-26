"""Tests for multi-tranche execution (ADD / TRIM / MOVE_STOP) in PaperTrader + Portfolio.

These assert ACCOUNTING INVARIANTS that are independent of the charge schedule and of
average-cost-vs-FIFO, so they stay true even if costs.py changes:
  - Cash conservation: final cash == initial + lifetime realized P&L (the single tripwire
    for commission double-counting / TRIM proration bugs).
  - Lifetime realized = sum of the legs (a TRIMmed-then-closed position books both).
  - A TRIM is NOT a closed trade (no win/loss tally until the final close).
  - MOVE_STOP is tighten-only and the mechanical floor fires at the MOVED stop.
Drives the real PaperTrader with synthetic signals — no LLM, no brain.
"""

from pytest import approx

from src.execution.executor import PaperTrader
from src.platform.config import PAPER_TRADE_SLIPPAGE, MIN_TRADE_VALUE


def _trader():
    return PaperTrader(initial_capital=50_000.0)


def _add(trader, symbol, qty, price):
    return trader.execute_trade({'symbol': symbol, 'signal': 'ADD', 'position_size': qty}, price)


def _trim(trader, symbol, frac, price):
    return trader.execute_trade({'symbol': symbol, 'signal': 'TRIM', 'trim_fraction': frac}, price)


def _move_stop(trader, symbol, new_stop, price):
    return trader.execute_trade({'symbol': symbol, 'signal': 'MOVE_STOP', 'new_stop': new_stop}, price)


# ----- the core lifecycle: BUY -> ADD -> TRIM -> full close ------------------------

def test_lifecycle_cash_conservation_and_lifetime_realized():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 10)
    _add(t, "T", 6, 520.0)
    trim = _trim(t, "T", 0.5, 540.0)
    assert trim["status"] == "EXECUTED" and trim["action"] == "TRIM"

    sell = t.execute_trade({'symbol': 'T', 'signal': 'SELL'}, 560.0)
    assert sell["status"] == "EXECUTED"

    closed = t.book.closed_trades[-1]
    # The position booked a partial gain while still open, then closed for the rest.
    assert closed.realized_pnl_partial != 0.0
    assert closed.total_buy_quantity == 16

    # Exactly ONE win/loss tally for the whole lifecycle — the TRIM must not bump it.
    assert t.book.winning_trades + t.book.losing_trades == 1

    # No open positions left -> all account value is cash, and the only money movement
    # over the lifecycle is realized P&L. This ties the reported LIFETIME realized to
    # the actual cash delta: catches commission double-count and TRIM-proration bugs.
    assert t.book.available_capital == approx(t.book.current_capital)
    assert t.book.current_capital == approx(50_000.0 + closed.realized_pnl)


def test_add_reaverages_cost_on_fill_price():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 10)
    _add(t, "T", 6, 520.0)
    pos = t.book.open_positions["T"]
    s = 1 + PAPER_TRADE_SLIPPAGE  # BUY/ADD fills pay up by slippage
    expected_avg = (10 * 500.0 * s + 6 * 520.0 * s) / 16
    assert pos.quantity == 16
    assert pos.entry_price == approx(expected_avg)


def test_trim_keeps_position_open_with_correct_remainder():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 20)
    res = _trim(t, "T", 0.25, 540.0)  # 25% of 20 = 5 trimmed, 15 remain
    assert res["quantity"] == 5
    assert res["remaining_quantity"] == 15
    assert t.has_position("T")
    assert t.book.open_positions["T"].quantity == 15
    # A partial exit is not a closed trade yet.
    assert t.book.closed_trades == []
    assert t.book.winning_trades + t.book.losing_trades == 0


# ----- TRIM guards ----------------------------------------------------------------

def test_trim_too_small_is_rejected_not_a_zero_share_fill():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 10)
    res = _trim(t, "T", 0.05, 540.0)  # int(10 * 0.05) == 0
    assert res["status"] == "REJECTED"
    assert t.book.open_positions["T"].quantity == 10  # untouched


def test_trim_leaving_sub_min_remnant_escalates_to_full_sell():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 12)  # value 6000
    # 90% trim -> 10 shares, remainder 2*~500 = ~1000 < MIN_TRADE_VALUE -> full exit.
    res = _trim(t, "T", 0.9, 540.0)
    assert res["action"] == "SELL"
    assert not t.has_position("T")
    assert MIN_TRADE_VALUE == 3000.0  # guard the premise of this test


# ----- MOVE_STOP: tighten-only, and the floor honors the moved stop ---------------

def test_move_stop_tightens_and_rejects_loosening_or_insta_trigger():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 10, 490.0, 515.0)  # stop 490, target 515

    assert _move_stop(t, "T", 495.0, 540.0)["status"] == "EXECUTED"
    assert t.book.open_positions["T"].stop_loss == approx(495.0)

    # Does not tighten (<= current 495) -> reject.
    assert _move_stop(t, "T", 492.0, 540.0)["status"] == "REJECTED"
    # At/above market -> disguised market exit -> reject.
    assert _move_stop(t, "T", 545.0, 540.0)["status"] == "REJECTED"
    assert t.book.open_positions["T"].stop_loss == approx(495.0)  # unchanged by rejects


def test_mechanical_floor_fires_at_the_moved_stop():
    t = _trader()
    t.execute_simple_trade("T", "BUY", 500.0, 10, 490.0, 515.0)
    _move_stop(t, "T", 495.0, 540.0)
    # Price 494 is above the ORIGINAL stop (490) but below the MOVED stop (495):
    # proves the floor reads the mutated stop.
    closed = t.update_positions({"T": 494.0})
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "STOP_LOSS"
    assert not t.has_position("T")
