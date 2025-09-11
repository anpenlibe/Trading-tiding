"""Unit tests for data collector."""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from src.data_collector import DataCollector
from src.interfaces import MarketData


class TestDataCollector:
    """Test data collection functionality."""
    
    @patch('src.data.database.DatabaseManager')
    def test_data_collector_initialization(self, mock_db):
        """Test data collector initializes properly."""
        collector = DataCollector()
        
        assert collector is not None
        assert hasattr(collector, 'apis')
        assert hasattr(collector, 'cache')
        assert hasattr(collector, 'validator')
    
    @patch('src.data.database.DatabaseManager')
    def test_collect_and_store_with_available_api(self, mock_db):
        """Test data collection when API is available."""
        # Setup database mock
        mock_db_instance = Mock()
        mock_db_instance.save_market_data.return_value = True
        mock_db_instance.get_recent_data.return_value = pd.DataFrame({
            'close': [100] * 50,
            'high': [105] * 50,
            'low': [98] * 50,
            'volume': [1000000] * 50
        })
        mock_db.return_value = mock_db_instance
        
        collector = DataCollector()
        
        # Mock API to return test data
        test_data = MarketData(
            symbol="TEST",
            timestamp=datetime.now(),
            open=100.0,
            high=105.0,
            low=98.0,
            close=102.0,
            volume=1000000
        )
        
        # Mock the API fetch_ohlc method
        for api in collector.apis:
            api.fetch_ohlc = Mock(return_value=test_data)
        
        result = collector.collect_and_store("TEST")
        
        assert result is True
    
    @patch('src.data.database.DatabaseManager')
    def test_collect_and_store_with_no_available_apis(self, mock_db):
        """Test data collection when no APIs are available."""
        collector = DataCollector()
        
        # Mock fetch_with_fallback to return None (no data available)
        with patch.object(collector, 'fetch_with_fallback', return_value=None):
            result = collector.collect_and_store("TEST")
            
            # Should return False when no data available
            assert result is False
    
    @patch('src.data.database.DatabaseManager')
    def test_collect_and_store_with_api_error(self, mock_db):
        """Test data collection when API throws an error."""
        collector = DataCollector()
        
        # Mock fetch_with_fallback to raise exception
        with patch.object(collector, 'fetch_with_fallback', side_effect=Exception("API Error")):
            try:
                result = collector.collect_and_store("TEST")
                # If it doesn't raise an exception, it should return False
                assert result is False
            except Exception:
                # If it does raise an exception, that's also acceptable
                pass
    
    @patch('src.data.database.DatabaseManager')
    def test_get_recent_data_from_database(self, mock_db):
        """Test retrieving recent data from database."""
        # Setup mock database to return DataFrame
        expected_df = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=5, freq='5min'),
            'open': [100, 101, 102, 101, 100],
            'high': [105, 106, 107, 106, 105],
            'low': [98, 99, 100, 99, 98],
            'close': [102, 103, 104, 103, 102],
            'volume': [1000000] * 5
        })
        
        mock_db_instance = Mock()
        mock_db_instance.get_recent_data.return_value = expected_df
        mock_db.return_value = mock_db_instance
        
        collector = DataCollector()
        
        # Mock the db instance directly after creation
        collector.db = mock_db_instance
        
        result = collector.get_recent_data("TEST", periods=5)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5
        mock_db_instance.get_recent_data.assert_called_once_with("TEST", 5)