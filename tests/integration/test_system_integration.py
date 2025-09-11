"""Simplified integration tests for the complete trading system."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from src.core.ai_brain import ClaudeAI
from src.core.paper_trader import PaperTrader
from src.core.risk_manager import SimpleRiskManager
from src.data_collector import DataCollector


class TestSystemIntegration:
    """Test complete system integration with simplified scenarios."""
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_complete_trading_workflow(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test the complete workflow from data to trade execution."""
        # Mock AI response
        mock_response = Mock()
        mock_response.content = [Mock(text='{"signal": "BUY", "confidence": 0.75, "reasoning": "Bullish trend"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        # Add required symbol column
        sample_df_data['symbol'] = 'TEST'
        
        # Initialize system components
        ai = ClaudeAI()
        trader = PaperTrader(initial_capital=10000)
        risk_manager = SimpleRiskManager()
        
        # Get current price
        current_price = float(sample_df_data['close'].iloc[-1])
        initial_capital = trader.available_capital
        
        # Step 1: AI makes decision
        decision = ai.analyze(sample_df_data, sample_indicators)
        assert decision['signal'] == "BUY"
        assert decision['confidence'] == 0.75
        
        # Step 2: Risk manager calculates position
        risk_params = risk_manager.calculate_risk_parameters(
            symbol="TEST",
            signal_type=decision['signal'],
            entry_price=current_price,
            capital=trader.available_capital
        )
        assert risk_params.position_size > 0
        assert risk_params.stop_loss < current_price  # Stop loss below entry for BUY
        assert risk_params.target > current_price      # Target above entry for BUY
        
        # Step 3: Execute trade
        result = trader.execute_simple_trade(
            symbol="TEST",
            action="BUY",
            price=current_price,
            quantity=risk_params.position_size
        )
        
        # Verify trade execution
        assert result.get('status') in ["EXECUTED", "REJECTED"]
        if result.get('status') == "EXECUTED":
            assert trader.available_capital < initial_capital  # Use available_capital instead
            assert "TEST" in trader.open_positions
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_risk_rejection_workflow(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test workflow when risk manager rejects a trade."""
        # Mock high-risk signal
        mock_response = Mock()
        mock_response.content = [Mock(text='{"signal": "BUY", "confidence": 0.9, "reasoning": "High risk trade"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        sample_df_data['symbol'] = 'TEST'
        
        # Initialize with low capital to trigger rejection
        ai = ClaudeAI()
        trader = PaperTrader(initial_capital=100)  # Low capital
        risk_manager = SimpleRiskManager()
        
        current_price = 1000.0  # High price relative to capital
        
        # AI decision
        decision = ai.analyze(sample_df_data, sample_indicators)
        assert decision['signal'] == "BUY"
        
        # Risk calculation - should be very small position
        risk_params = risk_manager.calculate_risk_parameters(
            symbol="TEST",
            signal_type=decision['signal'],
            entry_price=current_price,
            capital=trader.available_capital
        )
        
        # Attempt trade execution - likely to be rejected due to insufficient capital
        result = trader.execute_simple_trade(
            symbol="TEST",
            action="BUY",
            price=current_price,
            quantity=risk_params.position_size
        )
        
        # Should be rejected due to insufficient capital
        assert result.get('status') == "REJECTED"
        assert 'capital' in result.get('reason', '').lower()
    
    def test_data_processing_pipeline(self, sample_df_data):
        """Test data flows correctly through processing pipeline."""
        from src.core.indicator_engine import calculate_all_indicators
        
        # Process data through indicator engine
        indicators = calculate_all_indicators(sample_df_data)
        
        # Verify essential indicators are calculated
        assert isinstance(indicators, dict)
        assert len(indicators) > 0
        
        # Check key indicators exist
        essential_indicators = ['rsi_14', 'macd', 'sma_20']
        for indicator in essential_indicators:
            assert indicator in indicators
            assert indicators[indicator] is not None