"""Regression tests for the trading-mode safety system.

Safety-critical: pins that LIVE mode forbids mock data both at config level
(__post_init__ derives flags from mode, overriding any passed in) and at
runtime validation, while PAPER tolerates it. Also pins the removal of the dead
create_trading_mode_from_config helper.
"""

from datetime import datetime

import pytest

import src.core.trading_modes as tm
from src.core.trading_modes import (
    TradingMode,
    TradingSafetyConfig,
    TradingSafetyValidator,
    PAPER_TRADING_CONFIG,
    LIVE_TRADING_CONFIG,
    BACKTEST_CONFIG,
)
from src.interfaces import MarketData
from src.exceptions import TradingSystemError


def _bar(source):
    return MarketData("TCS", datetime.now(), 100, 101, 99, 100, 1000, source=source)


def test_mode_is_authoritative_over_passed_flags():
    """__post_init__ must force LIVE's flags regardless of what's passed in —
    a caller can't sneak mock fallback into live trading."""
    cfg = TradingSafetyConfig(mode=TradingMode.LIVE, allow_mock_fallback=True,
                              require_live_data=False, require_user_confirmation=False)
    assert cfg.allow_mock_fallback is False
    assert cfg.require_live_data is True
    assert cfg.require_user_confirmation is True


def test_default_configs_have_correct_safety_flags():
    assert PAPER_TRADING_CONFIG.allow_mock_fallback is True
    assert LIVE_TRADING_CONFIG.allow_mock_fallback is False
    assert LIVE_TRADING_CONFIG.require_live_data is True
    assert BACKTEST_CONFIG.allow_mock_fallback is False


def test_live_mode_rejects_mock_data():
    validator = TradingSafetyValidator(LIVE_TRADING_CONFIG)
    with pytest.raises(TradingSystemError):
        validator.validate_market_data(_bar("mock"))


def test_live_mode_accepts_zerodha_data():
    validator = TradingSafetyValidator(LIVE_TRADING_CONFIG)
    assert validator.validate_market_data(_bar("zerodha")) is True


def test_paper_mode_allows_mock_data():
    validator = TradingSafetyValidator(PAPER_TRADING_CONFIG)
    assert validator.validate_market_data(_bar("mock")) is True


def test_dead_helper_removed():
    assert not hasattr(tm, "create_trading_mode_from_config")
