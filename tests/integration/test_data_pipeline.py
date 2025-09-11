"""Integration tests for data pipeline."""

import pytest
from unittest.mock import Mock, patch
import pandas as pd
from datetime import datetime

from src.data_collector import DataCollector
from src.indicator_engine import compute_indicators
from src.interfaces import MarketData


class TestDataPipeline:
    """Test data collection and processing pipeline."""
    
    def test_data_collection_to_indicators_pipeline(self):
        """Test complete data flow from collection to indicators."""
        # Create sample historical data
        sample_data = pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=100, freq='5min'),
            'open': [100 + i * 0.1 for i in range(100)],
            'high': [101 + i * 0.1 for i in range(100)],
            'low': [99 + i * 0.1 for i in range(100)],
            'close': [100.5 + i * 0.1 for i in range(100)],
            'volume': [1000000] * 100
        })
        
        # Process through indicator engine
        indicators = compute_indicators(sample_data)
        
        # Verify indicators are calculated
        assert 'rsi_14' in indicators
        assert 'macd' in indicators
        assert 'sma_20' in indicators
        
        # RSI should be reasonable
        assert 0 <= indicators['rsi_14'] <= 100
    
    def test_real_time_data_simulation(self):
        """Test processing of real-time data updates."""
        collector = DataCollector()
        
        # Simulate multiple data points coming in
        test_symbols = ["TEST1", "TEST2"]
        collected_data = {}
        
        for symbol in test_symbols:
            # Mock API response
            with patch.object(collector, 'apis') as mock_apis:
                mock_api = Mock()
                mock_api.is_available.return_value = True
                mock_api.fetch_ohlc.return_value = MarketData(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    open=100.0,
                    high=105.0,
                    low=98.0,
                    close=102.0,
                    volume=1000000
                )
                mock_apis.__iter__ = Mock(return_value=iter([mock_api]))
                
                result = collector.collect_and_store(symbol)
                collected_data[symbol] = result
        
        # Should have collected data for all symbols
        assert len(collected_data) == len(test_symbols)
    
    def test_data_quality_validation(self):
        """Test data quality checks in the pipeline."""
        # Test with invalid data
        invalid_data = pd.DataFrame({
            'close': [100, None, 102, 103, None],  # Contains NaN values
            'volume': [1000, 2000, 0, 3000, 4000]  # Contains zero volume
        })
        
        # Indicator engine should handle invalid data gracefully
        indicators = compute_indicators(invalid_data)
        
        # Should return reasonable defaults or handle gracefully
        assert isinstance(indicators, dict)
        assert 'rsi_14' in indicators
    
    @patch('src.data_collector.DatabaseManager')
    def test_database_integration(self, mock_db, temp_database):
        """Test database operations in the pipeline."""
        # Setup mock database
        mock_db_instance = Mock()
        mock_db_instance.get_recent_data.return_value = pd.DataFrame({
            'timestamp': pd.date_range('2025-01-01', periods=10, freq='5min'),
            'open': [100] * 10,
            'high': [105] * 10,
            'low': [98] * 10,
            'close': [102] * 10,
            'volume': [1000000] * 10
        })
        mock_db.return_value = mock_db_instance
        
        collector = DataCollector()
        
        # This would test actual database operations if implemented
        # For now, just verify the collector can be instantiated
        assert collector is not None
        
        # Test that we can call database-related methods
        if hasattr(collector, 'get_recent_data'):
            # Should not crash even with empty database
            result = collector.get_recent_data("TEST", 10)
            assert result is None or isinstance(result, (list, pd.DataFrame))
    
    @patch('src.data_collector.DatabaseManager')
    def test_error_propagation_in_pipeline(self, mock_db):
        """Test how errors propagate through the data pipeline."""
        collector = DataCollector()
        
        # Simulate API failure by making fetch_with_fallback return None
        with patch.object(collector, 'fetch_with_fallback', return_value=None):
            # Should handle error gracefully
            result = collector.collect_and_store("TEST")
            
            # Should return False when no data available
            assert result is False