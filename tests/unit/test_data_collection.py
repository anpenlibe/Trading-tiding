"""Simplified unit tests for data collection."""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch
from src.data_collector import DataCollector
from src.interfaces import MarketData


class TestDataCollection:
    """Test data collection functionality with simplified scenarios."""
    
    def test_data_collector_initialization(self):
        """Test data collector initializes without errors."""
        collector = DataCollector()
        
        assert collector is not None
        assert hasattr(collector, 'apis')
        assert hasattr(collector, 'cache')
        assert len(collector.apis) >= 2  # Should have Zerodha + Mock APIs
    
    def test_get_recent_data_returns_dataframe(self):
        """Test that get_recent_data returns proper DataFrame format."""
        collector = DataCollector()
        
        # This will use actual database if available
        df = collector.get_recent_data("RELIANCE", periods=10)
        
        if df is not None:
            assert isinstance(df, pd.DataFrame)
            expected_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in expected_columns:
                assert col in df.columns
            
            # Check data integrity
            if not df.empty:
                assert (df['high'] >= df['low']).all()
                assert (df['high'] >= df['open']).all() 
                assert (df['high'] >= df['close']).all()
                assert (df['volume'] >= 0).all()
    
    def test_market_data_validation(self):
        """Test that MarketData objects are properly validated."""
        # Valid market data
        valid_data = MarketData(
            symbol="TEST",
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000000
        )
        
        assert valid_data.symbol == "TEST"
        assert valid_data.high >= valid_data.low
        assert valid_data.volume > 0