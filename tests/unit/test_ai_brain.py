"""Unit tests for AI brain."""

import pytest
import json
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch
from src.core.ai_brain import ClaudeAI
from src.interfaces import MarketData


class TestClaudeAI:
    """Test AI decision making functionality."""
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_ai_initialization(self, mock_anthropic):
        """Test AI brain initializes properly."""
        ai = ClaudeAI()
        
        assert ai is not None
        mock_anthropic.assert_called_once()
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_analyze_with_buy_signal(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test AI analysis with buy signal response."""
        # Mock the API response
        mock_response = Mock()
        mock_response.content = [Mock(text='{"signal": "BUY", "confidence": 0.75, "reasoning": "Bullish indicators"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        # Add symbol column to DataFrame
        sample_df_data['symbol'] = 'TEST'
        
        ai = ClaudeAI()
        result = ai.analyze(sample_df_data, sample_indicators)
        
        assert result['signal'] == "BUY"
        assert result['confidence'] == 0.75
        assert 'reasoning' in result
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_analyze_with_sell_signal(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test AI analysis with sell signal response."""
        mock_response = Mock()
        mock_response.content = [Mock(text='{"signal": "SELL", "confidence": 0.6, "reasoning": "Bearish trend"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        # Add symbol column to DataFrame
        sample_df_data['symbol'] = 'TEST'
        
        ai = ClaudeAI()
        result = ai.analyze(sample_df_data, sample_indicators)
        
        assert result['signal'] == "SELL"
        assert result['confidence'] == 0.6
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_analyze_with_hold_signal(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test AI analysis with hold signal response."""
        mock_response = Mock()
        mock_response.content = [Mock(text='{"signal": "HOLD", "confidence": 0.5, "reasoning": "Sideways market"}')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        # Add symbol column to DataFrame
        sample_df_data['symbol'] = 'TEST'
        
        ai = ClaudeAI()
        result = ai.analyze(sample_df_data, sample_indicators)
        
        assert result['signal'] == "HOLD"
        assert result['confidence'] == 0.5
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_analyze_with_invalid_json(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test AI analysis handles invalid JSON response."""
        mock_response = Mock()
        mock_response.content = [Mock(text='Invalid JSON response')]
        mock_anthropic.return_value.messages.create.return_value = mock_response
        
        # Add symbol column to DataFrame
        sample_df_data['symbol'] = 'TEST'
        
        ai = ClaudeAI()
        result = ai.analyze(sample_df_data, sample_indicators)
        
        # Should return safe defaults or handle error gracefully
        assert isinstance(result, dict)
        assert result.get('signal') == 'HOLD'
        assert result.get('confidence') == 0.0
    
    @patch('src.core.ai_brain.anthropic.Anthropic')
    def test_analyze_with_api_error(self, mock_anthropic, sample_df_data, sample_indicators):
        """Test AI analysis handles API errors."""
        mock_anthropic.return_value.messages.create.side_effect = Exception("API Error")
        
        # Add symbol column to DataFrame
        sample_df_data['symbol'] = 'TEST'
        
        ai = ClaudeAI()
        result = ai.analyze(sample_df_data, sample_indicators)
        
        # Should handle error gracefully
        assert isinstance(result, dict)
        assert result.get('signal') == 'HOLD'
        assert result.get('confidence') == 0.0
        assert 'error' in result.get('reasoning', '').lower()