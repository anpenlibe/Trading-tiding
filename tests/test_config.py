"""Regression tests for config helpers.

Pins the wrong-import-path bug: get_trading_symbols / get_symbol_info imported
from `src.stock_registry` (nonexistent) behind a broad except, so they silently
returned degraded data instead of reaching the real registry.
"""


def test_get_symbol_info_returns_real_data():
    from src.data.config import get_symbol_info
    info = get_symbol_info('TCS')
    assert info, "get_symbol_info('TCS') should not be empty (registry reachable)"
    assert info['symbol'] == 'TCS'
    assert 'sector' in info


def test_get_trading_symbols_conservative():
    from src.data.config import get_trading_symbols
    symbols = get_trading_symbols('conservative')
    assert isinstance(symbols, list) and len(symbols) > 0
    assert all(isinstance(s, str) for s in symbols)


def test_consumed_knobs_have_expected_defaults():
    """The risk/cost knobs we env-drove must keep their documented defaults."""
    from src.data import config as c
    assert c.MAX_POSITION_SIZE == 0.20
    assert c.STOP_LOSS_PERCENT == 0.015
    assert c.TAKE_PROFIT_PERCENT == 0.03


def test_removed_dead_constant_is_gone():
    from src.data import config as c
    assert not hasattr(c, 'MAX_POSITION_SIZE_PERCENT')
