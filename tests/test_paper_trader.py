"""Regression tests for PaperTrader.

Pins the position-close bugs fixed during the god-node pass: mid-iteration
mutation on auto-close, capital double-counting, and partial-sell share loss.
"""


def _buy(trader, symbol='TCS', price=100.0, qty=2, stop_loss=95.0, target=110.0):
    return trader.execute_simple_trade(
        symbol, 'BUY', price, quantity=qty, stop_loss=stop_loss, target=target,
    )


class TestBuyExecution:
    def test_buy_opens_position_and_spends_capital(self, fresh_trader):
        res = _buy(fresh_trader)
        assert res['status'] == 'EXECUTED'
        assert 'TCS' in fresh_trader.open_positions
        assert fresh_trader.available_capital < 10000.0

    def test_duplicate_buy_rejected(self, fresh_trader):
        _buy(fresh_trader)
        res = _buy(fresh_trader)
        assert res['status'] == 'REJECTED'


class TestSellExecution:
    def test_sell_closes_full_position(self, fresh_trader):
        """A SELL of fewer shares than held must still close the whole
        position (partial sell used to delete the position but only account
        for the requested qty, vanishing shares)."""
        _buy(fresh_trader, qty=3)
        res = fresh_trader.execute_simple_trade('TCS', 'SELL', 105.0, quantity=1)
        assert res['status'] == 'EXECUTED'
        assert res['quantity'] == 3
        assert 'TCS' not in fresh_trader.open_positions

    def test_sell_without_position_rejected(self, fresh_trader):
        res = fresh_trader.execute_simple_trade('TCS', 'SELL', 105.0, quantity=1)
        assert res['status'] == 'REJECTED'


class TestAutoClose:
    def test_stop_loss_auto_close_no_crash(self, fresh_trader):
        """update_positions iterates while _execute_sell deletes from the same
        dict — must not raise RuntimeError (dict changed size)."""
        _buy(fresh_trader, qty=2, stop_loss=95.0, target=110.0)
        fresh_trader.update_positions({'TCS': 94.0})  # below stop
        assert 'TCS' not in fresh_trader.open_positions
        assert fresh_trader.losing_trades == 1

    def test_target_auto_close(self, fresh_trader):
        _buy(fresh_trader, qty=2, stop_loss=95.0, target=110.0)
        fresh_trader.update_positions({'TCS': 111.0})  # above target
        assert 'TCS' not in fresh_trader.open_positions
        assert fresh_trader.winning_trades == 1

    def test_capital_consistent_after_close(self, fresh_trader):
        """After a full close with no open positions, current_capital must
        equal available_capital (no double-counting of the closed position)."""
        _buy(fresh_trader, qty=2)
        fresh_trader.update_positions({'TCS': 111.0})  # target hit -> close
        assert not fresh_trader.open_positions
        assert abs(fresh_trader.current_capital - fresh_trader.available_capital) < 1e-6


class TestContractAndGuards:
    def test_missing_symbol_rejected(self, fresh_trader):
        """A signal with no symbol must be rejected, not opened as a None-keyed
        phantom position ("BUY executed: None x1")."""
        res = fresh_trader.execute_trade({'signal': 'BUY', 'position_size': 1}, 100.0)
        assert res['status'] == 'REJECTED'
        assert fresh_trader.open_positions == {}

    def test_place_order_delegates_to_execution(self, fresh_trader):
        """The BaseTradingExecutor contract method now actually trades (was a
        no-op stub) and rejects a priceless paper order."""
        res = fresh_trader.place_order('TCS', 2, 'BUY', price=100.0)
        assert res['status'] == 'EXECUTED'
        assert 'TCS' in fresh_trader.open_positions
        assert fresh_trader.place_order('INFY', 1, 'BUY', price=None)['status'] == 'REJECTED'


class TestPnLTracking:
    def test_current_capital_fresh_after_buy(self, fresh_trader):
        """current_capital must be recomputed right after a BUY (not left stale
        until the next update/sell). With zero commission/slippage it should be
        ~unchanged: cash spent == position market value."""
        _buy(fresh_trader, qty=2, price=100.0)
        assert abs(fresh_trader.current_capital - 10000.0) < 1e-6

    def test_round_trip_pnl_matches_capital(self, fresh_trader):
        """Realized P&L of a full round-trip must equal the capital gained.
        ~10 shares * (110-100) = 100, less slippage on both legs (~Re 1)."""
        _buy(fresh_trader, qty=10, price=100.0, stop_loss=None, target=None)
        res = fresh_trader.execute_simple_trade('TCS', 'SELL', 110.0, quantity=10)
        assert res['status'] == 'EXECUTED'
        assert 98.0 < res['realized_pnl'] <= 100.0  # gross 100 minus slippage
        # The invariant that must hold exactly: capital gained == realized P&L.
        assert abs(fresh_trader.current_capital - (10000.0 + res['realized_pnl'])) < 1e-6

    def test_drawdown_tracked_mark_to_market(self, fresh_trader):
        """max_drawdown must reflect an unrealized dip (mark-to-market), not only
        realized losses at sell time."""
        _buy(fresh_trader, qty=10, price=100.0, stop_loss=None, target=None)
        fresh_trader.update_positions({'TCS': 80.0})  # 20% unrealized dip, no close
        assert 'TCS' in fresh_trader.open_positions   # still open
        assert fresh_trader.max_drawdown > 0           # dip captured
