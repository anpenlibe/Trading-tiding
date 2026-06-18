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


def test_vestigial_config_removed():
    """Pins the cleanup removals: an unused mean-reversion STRATEGIES dict, a
    legacy MIN_TRADE_VALUE_TEST, and DATA_SOURCE_PRIORITY (priority lives in
    DataCollector._init_apis). All had zero references and no .env.example entry."""
    from src.data import config as c
    for name in ('STRATEGIES', 'MIN_TRADE_VALUE_TEST', 'DATA_SOURCE_PRIORITY'):
        assert not hasattr(c, name), f"{name} was vestigial and should stay removed"


def test_core_config_surface_intact():
    """The documented config surface must remain importable."""
    from src.data import config as c
    for name in ('INITIAL_CAPITAL', 'SYMBOLS', 'MAX_RISK_PER_TRADE', 'DB_PATH',
                 'BUNDLED_DB_PATH', 'TRADING_MODE', 'CACHE_TTL_SECONDS'):
        assert hasattr(c, name), f"{name} is part of the public config surface"
