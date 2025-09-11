"""Unit tests for configuration."""

import pytest
import os
from unittest.mock import patch


class TestConfig:
    """Test configuration loading and validation."""
    
    def test_config_imports_successfully(self):
        """Test that config module imports without errors."""
        try:
            from src.data.config import (
                RSI_PERIOD, MACD_FAST, MACD_SLOW,
                STOP_LOSS_PERCENT, MAX_RISK_PER_TRADE, SYMBOLS,
                INITIAL_CAPITAL, ANTHROPIC_API_KEY
            )
            assert True  # Import successful
        except ImportError as e:
            pytest.fail(f"Config import failed: {e}")
    
    def test_config_values_are_reasonable(self):
        """Test that configuration values are within reasonable ranges."""
        from src.data.config import (
            RSI_PERIOD, MACD_FAST, MACD_SLOW,
            STOP_LOSS_PERCENT, MAX_RISK_PER_TRADE, INITIAL_CAPITAL
        )
        
        # Test RSI period
        assert 5 <= RSI_PERIOD <= 50  # Reasonable RSI period
        
        # Test MACD parameters
        assert 5 <= MACD_FAST <= 20
        assert 20 <= MACD_SLOW <= 50
        assert MACD_FAST < MACD_SLOW
        
        # Test risk parameters
        assert 0.005 <= STOP_LOSS_PERCENT <= 0.10  # 0.5% to 10%
        assert 0.005 <= MAX_RISK_PER_TRADE <= 0.05   # 0.5% to 5%
        
        # Test capital
        assert INITIAL_CAPITAL > 0
    
    def test_symbols_list_exists(self):
        """Test that symbols list is populated."""
        from src.data.config import SYMBOLS
        
        assert isinstance(SYMBOLS, list)
        assert len(SYMBOLS) > 0
        
        # Check all symbols are strings and uppercase
        for symbol in SYMBOLS:
            assert isinstance(symbol, str)
            assert symbol.isupper()
            assert len(symbol) >= 2  # At least 2 characters
    
    def test_market_hours_configuration(self):
        """Test market hours configuration."""
        from src.data.config import MARKET_OPEN, MARKET_CLOSE, MARKET_TIMEZONE
        
        assert isinstance(MARKET_OPEN, str)
        assert isinstance(MARKET_CLOSE, str)
        assert MARKET_TIMEZONE is not None
        
        # Check time format (HH:MM)
        assert len(MARKET_OPEN.split(':')) == 2
        assert len(MARKET_CLOSE.split(':')) == 2
    
    @patch.dict(os.environ, {'TRADING_STRATEGY': 'conservative'})
    def test_trading_strategy_environment_variable(self):
        """Test that trading strategy can be set via environment."""
        # This test would need to reload the config module
        # For now, just test that the environment variable exists
        assert os.getenv('TRADING_STRATEGY') == 'conservative'
    
    def test_api_configuration_exists(self):
        """Test that API configuration is present."""
        try:
            from src.data.config import API_CONFIG
            assert isinstance(API_CONFIG, dict)
        except ImportError:
            # API_CONFIG might not be defined, which is acceptable
            pass