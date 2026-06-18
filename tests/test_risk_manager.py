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

    def test_overpriced_stock_rejected_with_honest_reason(self, risk_manager):
        """A share priced above the per-position cap must be skipped with an
        honest 'exceeds max position' reason — NOT the misleading
        '₹0.00 below minimum' message, which blamed capital instead of the
        stock's price (position sizing returns 0 shares for it)."""
        # ₹4,000 share vs 20% of ₹10,000 = ₹2,000 cap → unaffordable within cap
        signal = {'symbol': 'LT', 'signal': 'BUY', 'entry_price': 4000.0,
                  'available_capital': 10000.0}
        is_valid, reason = risk_manager.validate_trade(signal, {})
        assert is_valid is False
        assert 'exceeds max position' in reason.lower()
        assert '0.00 below minimum' not in reason

    def test_overpriced_stock_tradeable_at_larger_capital(self, risk_manager):
        """The capital-adaptive flip side: the SAME expensive stock becomes
        tradeable once capital is large enough that one share fits within the
        cap. The cap is fixed; the tradeable universe adapts to capital."""
        signal = {'symbol': 'LT', 'signal': 'BUY', 'entry_price': 4000.0,
                  'available_capital': 100000.0}  # 20% = ₹20,000 > ₹4,000
        is_valid, _ = risk_manager.validate_trade(signal, {})
        assert is_valid is True


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
