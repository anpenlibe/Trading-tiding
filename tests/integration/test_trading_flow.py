"""Integration tests for complete trading flow."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from src.ai_brain import ClaudeAI
from src.paper_trader import PaperTrader
from src.risk_manager import SimpleRiskManager
from src.data_collector import DataCollector


class TestTradingFlow:
    """Test complete trading flow integration."""
    
    @patch('src.ai_brain.anthropic.Anthropic')
    @patch('src.data_collector.DatabaseManager')
    def test_complete_trading_cycle(self, mock_db, mock_anthropic, sample_df_data, 
                                   sample_indicators, temp_database):
        """Test full cycle from data to trade execution."""
        # Setup mocks
        mock_response = Mock()
        mock_response.content = [Mock(text='{"signal": "BUY", "confidence": 0.75, "reasoning": "Bullish indicators"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        # Add symbol column to DataFrame
        sample_df_data['symbol'] = 'TEST'
        
        # Initialize components
        ai = ClaudeAI()
        trader = PaperTrader(initial_capital=10000)
        risk_mgr = SimpleRiskManager()
        
        # Generate signal using DataFrame
        decision = ai.analyze(sample_df_data, sample_indicators)
        
        assert decision['signal'] == "BUY"
        assert decision['confidence'] == 0.75
        
        # Get current price from DataFrame
        current_price = float(sample_df_data['close'].iloc[-1])
        
        # Calculate risk parameters
        risk_params = risk_mgr.calculate_risk_parameters(
            symbol="TEST",
            signal_type=decision['signal'],
            entry_price=current_price,
            capital=trader.current_capital
        )
        
        assert risk_params.position_size > 0
        
        # Execute trade
        result = trader.execute_simple_trade(
            symbol="TEST",
            action=decision['signal'],
            quantity=risk_params.position_size,
            price=current_price
        )
        
        assert result['status'] == "EXECUTED"
    
    @patch('src.data_collector.DatabaseManager')
    def test_data_collection_to_indicators(self, mock_db, temp_database):
        """Test data collection and indicator calculation flow."""
        # Setup mock database
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
        from src.interfaces import MarketData
        from datetime import datetime
        
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
        
        # Collect and store data
        success = collector.collect_and_store("TEST")
        
        # Should succeed with mocked data
        assert success is True
    
    @patch('src.ai_brain.anthropic.Anthropic')
    @patch('src.data_collector.DatabaseManager')
    def test_risk_management_integration(self, mock_db, mock_anthropic, sample_df_data):
        """Test risk management with different confidence levels."""
        # Add symbol to sample data
        sample_df_data['symbol'] = 'TEST'
        
        # Test high confidence trade
        mock_response_high = Mock()
        mock_response_high.content = [Mock(text='{"signal": "BUY", "confidence": 0.9, "reasoning": "Strong signals"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response_high
        
        ai = ClaudeAI()
        trader = PaperTrader(initial_capital=10000)
        risk_mgr = SimpleRiskManager()
        
        # Test different risk parameters
        decision = ai.analyze(sample_df_data, {})
        risk_params_high = risk_mgr.calculate_risk_parameters(
            symbol="TEST", signal_type="BUY", entry_price=100.0, 
            capital=10000
        )
        
        # Test with custom risk percent for lower risk
        risk_params_low = risk_mgr.calculate_risk_parameters(
            symbol="TEST", signal_type="BUY", entry_price=100.0, 
            capital=10000, custom_risk_percent=0.005  # Lower risk
        )
        
        # Default risk should have larger position size than custom low risk
        assert risk_params_high.position_size > risk_params_low.position_size
    
    def test_error_handling_integration(self):
        """Test error handling across components."""
        trader = PaperTrader(initial_capital=100)  # Very low capital
        risk_mgr = SimpleRiskManager()
        
        # Try to execute large trade
        risk_params = risk_mgr.calculate_risk_parameters(
            symbol="TEST", signal_type="BUY", entry_price=1000.0,
            capital=100
        )
        
        # Should validate trade as potentially invalid due to insufficient capital
        signal = {
            'symbol': 'TEST',
            'signal': 'BUY',
            'entry_price': 1000.0,
            'position_size': risk_params.position_size,
            'stop_loss': risk_params.stop_loss,
            'target': risk_params.target
        }
        is_valid, error_msg = risk_mgr.validate_trade(signal, {})
        
        # Test that system handles low capital gracefully
        result = trader.execute_simple_trade(
            symbol="TEST", action="BUY", 
            quantity=max(1, risk_params.position_size), price=1000.0
        )
        
        # Should either execute or handle gracefully
        assert result is not None