"""Regression tests for SimpleRiskManager.

Each test pins a bug fixed during the correctness pass — the failure modes here
were all "silent wrong" (no crash, just incorrect behaviour), which is exactly
what these guard against.
"""


class TestValidateTrade:
    def test_sell_on_held_symbol_is_allowed(self, risk_manager):
        """A SELL closes a position, so it must NOT be rejected just because we
        hold the symbol (the old bug blocked every exit)."""
        signal = {'symbol': 'TCS', 'signal': 'SELL', 'available_capital': 9000}
        positions = {'TCS': {'quantity': 5}}
        is_valid, reason = risk_manager.validate_trade(signal, positions)
        assert is_valid is True, reason

    def test_buy_on_already_held_symbol_is_rejected(self, risk_manager):
        """Opening a second position in a held symbol should still be blocked."""
        signal = {'symbol': 'TCS', 'signal': 'BUY', 'entry_price': 100.0,
                  'available_capital': 9000}
        positions = {'TCS': {'quantity': 5}}
        is_valid, reason = risk_manager.validate_trade(signal, positions)
        assert is_valid is False
        assert 'TCS' in reason

    def test_buy_without_entry_price_rejected_not_crash(self, risk_manager):
        """A BUY with no entry_price must be rejected cleanly, not raise
        TypeError (which callers swallowed as a silent non-execution)."""
        signal = {'symbol': 'INFY', 'signal': 'BUY', 'available_capital': 9000}
        is_valid, reason = risk_manager.validate_trade(signal, {})
        assert is_valid is False
        assert 'entry price' in reason.lower()

    def test_buy_with_entry_price_passes(self, risk_manager):
        signal = {'symbol': 'INFY', 'signal': 'BUY', 'entry_price': 100.0,
                  'available_capital': 9000}
        is_valid, _ = risk_manager.validate_trade(signal, {})
        assert is_valid is True

    def test_insufficient_capital_rejected(self, risk_manager):
        signal = {'symbol': 'INFY', 'signal': 'BUY', 'entry_price': 100.0,
                  'available_capital': 10.0}
        is_valid, reason = risk_manager.validate_trade(signal, {})
        assert is_valid is False
        assert 'capital' in reason.lower()


class TestPositionSizing:
    def test_position_respects_capital_cap(self, risk_manager):
        """Position value must never exceed MAX_POSITION_SIZE of capital."""
        from src.data.config import MAX_POSITION_SIZE
        rp = risk_manager.calculate_risk_parameters(
            symbol='TCS', signal_type='BUY', entry_price=100.0, capital=10000.0,
            stop_loss=95.0, target=110.0,
        )
        assert rp.position_value <= 10000.0 * MAX_POSITION_SIZE + 1e-6

    def test_zero_stop_distance_returns_zero(self, risk_manager):
        size = risk_manager.calculate_position_size(
            capital=10000.0, risk_per_trade=0.015, stop_loss_distance=0.0,
            entry_price=100.0,
        )
        assert size == 0
