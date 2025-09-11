"""Shared test fixtures for all test modules."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from src.interfaces import MarketData, TradingSignal
from src.core.paper_trader import PaperTrader
from src.core.risk_manager import SimpleRiskManager
from src.data_collector import DataCollector


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    return MarketData(
        symbol="TEST",
        timestamp=datetime.now(),
        open=100.0,
        high=105.0,
        low=98.0,
        close=102.0,
        volume=1000000
    )


@pytest.fixture
def sample_indicators():
    """Create sample indicators for testing."""
    return {
        'sma_20': 101.5,
        'sma_50': 100.8,
        'sma_200': 99.2,
        'rsi': 55.0,
        'macd': 0.5,
        'macd_signal': 0.3,
        'volume_ratio': 1.2
    }


@pytest.fixture
def sample_df_data():
    """Create sample DataFrame with price data."""
    dates = pd.date_range(end=datetime.now(), periods=50, freq='5min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(95, 105, 50),
        'high': np.random.uniform(100, 110, 50),
        'low': np.random.uniform(90, 100, 50),
        'close': np.random.uniform(95, 105, 50),
        'volume': np.random.uniform(900000, 1100000, 50)
    })
    # Ensure high/low logic
    df['high'] = df[['open', 'close', 'high']].max(axis=1)
    df['low'] = df[['open', 'close', 'low']].min(axis=1)
    return df


@pytest.fixture
def mock_claude_api():
    """Mock Claude API responses."""
    mock = MagicMock()
    mock.messages.create.return_value.content = [{
        "text": '{"signal": "BUY", "confidence": 0.75, "reasoning": "Test signal"}'
    }]
    return mock


@pytest.fixture
def paper_trader():
    """Create a paper trader instance for testing."""
    return PaperTrader(initial_capital=10000)


@pytest.fixture
def risk_manager():
    """Create a risk manager instance for testing."""
    return SimpleRiskManager()


@pytest.fixture
def temp_database(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_market_data.sqlite"
    return str(db_path)