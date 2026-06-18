"""Regression tests for the stock registry.

Pins the singleton accessor, the strategy-preset helpers (which back
config.SYMBOLS), sector lookup (incl. the invalid-sector -> [] path),
get_stock_info case-insensitivity, and the removal of the seven dead methods.
"""

from src.data.stock_registry import (
    StockRegistry,
    Sector,
    get_stock_registry,
    get_swing_trading_symbols,
    get_conservative_symbols,
    get_diversified_symbols,
    get_symbols_by_sector,
)


def test_registry_is_singleton():
    assert get_stock_registry() is get_stock_registry()


def test_strategy_helpers_return_symbol_lists():
    for helper in (get_swing_trading_symbols, get_conservative_symbols, get_diversified_symbols):
        symbols = helper()
        assert symbols and all(isinstance(s, str) for s in symbols)


def test_symbols_by_sector_and_invalid_sector():
    tech = get_symbols_by_sector("technology")
    assert "TCS" in tech and "INFY" in tech
    assert get_symbols_by_sector("not_a_sector") == []  # unknown sector -> empty


def test_get_stock_info_is_case_insensitive():
    reg = get_stock_registry()
    info = reg.get_stock_info("tcs")
    assert info is not None
    assert info.symbol == "TCS" and info.sector == Sector.TECHNOLOGY
    assert reg.get_stock_info("NOPE") is None


def test_removed_methods_stay_removed():
    reg = StockRegistry()
    for name in ("get_symbols_by_market_cap", "get_symbols_by_liquidity", "get_index_stocks",
                 "get_aggressive_portfolio", "get_sector_summary", "save_to_file", "load_from_file"):
        assert not hasattr(reg, name), f"{name} was dead and should stay removed"
