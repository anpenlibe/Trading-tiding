"""
Comprehensive tests for PromptBuilder, focusing on threshold assignment logic.

This test suite addresses auditor recommendations for testing all conditional paths,
particularly around emergency threshold extraction and assignment.
"""

import pytest
import pandas as pd
from unittest.mock import patch
from src.ai.prompt_builder import PromptBuilder


class TestExtractEmergencyThresholds:
    """Test the extract_emergency_thresholds method comprehensively."""

    def test_ai_provided_all_thresholds(self):
        """Test when AI provides all threshold values."""
        thresholds = {
            'stop_loss_pct': -2.5,
            'take_profit_pct': 5.0,
            'recheck_trigger_pct': 1.5,
            'comment': 'AI custom monitoring'
        }
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'HOLD')

        assert result['stop_loss_pct'] == -2.5
        assert result['take_profit_pct'] == 5.0
        assert result['recheck_trigger_pct'] == 1.5
        assert result['comment'] == 'AI custom monitoring'

    def test_ai_provided_partial_thresholds(self):
        """Test when AI provides some threshold values."""
        thresholds = {
            'stop_loss_pct': -4.0,
            'comment': 'Partial AI monitoring'
        }
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'HOLD')

        assert result['stop_loss_pct'] == -4.0
        assert result['take_profit_pct'] == 4.0  # Default
        assert result['recheck_trigger_pct'] == 2.0  # Default
        assert result['comment'] == 'Partial AI monitoring'

    def test_owned_position_no_ai_thresholds(self):
        """Test owned position with no AI-provided thresholds."""
        thresholds = {}
        result = PromptBuilder.extract_emergency_thresholds(thresholds, True, 'HOLD')

        assert result['stop_loss_pct'] == -3.5  # Default
        assert result['take_profit_pct'] == 4.0  # Default
        assert result['recheck_trigger_pct'] == 2.0  # Default
        assert result['comment'] == 'Standard monitoring'

    def test_active_signal_no_ai_thresholds(self):
        """Test BUY/SELL signals with no AI-provided thresholds."""
        thresholds = {}

        # Test BUY signal
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'BUY')
        assert result['stop_loss_pct'] == -3.5
        assert result['take_profit_pct'] == 4.0
        assert result['recheck_trigger_pct'] == 2.0
        assert result['comment'] == 'Standard monitoring'

        # Test SELL signal
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'SELL')
        assert result['stop_loss_pct'] == -3.5
        assert result['take_profit_pct'] == 4.0
        assert result['recheck_trigger_pct'] == 2.0
        assert result['comment'] == 'Standard monitoring'

    def test_unowned_hold_no_ai_thresholds(self):
        """Test unowned HOLD position with no AI thresholds - should not monitor."""
        thresholds = {}
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'HOLD')

        assert result['stop_loss_pct'] is None
        assert result['take_profit_pct'] is None
        assert result['recheck_trigger_pct'] is None
        assert result['comment'] is None

    def test_ai_zero_thresholds_treated_as_provided(self):
        """Test that AI-provided zero values are respected, not treated as None."""
        thresholds = {
            'stop_loss_pct': 0.0,  # AI explicitly set to zero
            'take_profit_pct': 0.0,
            'recheck_trigger_pct': 0.0
        }
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'HOLD')

        assert result['stop_loss_pct'] == 0.0  # AI's explicit zero
        assert result['take_profit_pct'] == 0.0
        assert result['recheck_trigger_pct'] == 0.0
        assert result['comment'] == 'Standard monitoring'

    def test_ai_none_values_use_defaults(self):
        """Test that AI-provided None values fall back to defaults when monitoring."""
        thresholds = {
            'stop_loss_pct': None,
            'take_profit_pct': 6.0,  # AI provided this one
            'comment': 'Mixed AI monitoring'
        }
        result = PromptBuilder.extract_emergency_thresholds(thresholds, True, 'HOLD')

        assert result['stop_loss_pct'] == -3.5  # Default (AI provided None)
        assert result['take_profit_pct'] == 6.0  # AI provided
        assert result['recheck_trigger_pct'] == 2.0  # Default (missing)
        assert result['comment'] == 'Mixed AI monitoring'

    def test_complex_combination_owned_with_partial_ai(self):
        """Test complex scenario: owned position with partial AI thresholds."""
        thresholds = {
            'take_profit_pct': 8.0,  # AI wants higher profit target
            'comment': 'Momentum play - higher target'
        }
        result = PromptBuilder.extract_emergency_thresholds(thresholds, True, 'BUY')

        assert result['stop_loss_pct'] == -3.5  # Default
        assert result['take_profit_pct'] == 8.0  # AI provided
        assert result['recheck_trigger_pct'] == 2.0  # Default
        assert result['comment'] == 'Momentum play - higher target'

    def test_edge_case_empty_comment_gets_default(self):
        """Test that empty comment gets default when monitoring is enabled."""
        thresholds = {
            'stop_loss_pct': -2.0,
            'comment': ''  # Empty string
        }
        result = PromptBuilder.extract_emergency_thresholds(thresholds, False, 'BUY')

        assert result['comment'] == 'Standard monitoring'  # Default applied


class TestPortfolioResponseParsing:
    """Test portfolio response parsing with comprehensive threshold scenarios."""

    def create_sample_portfolio_data(self):
        """Create sample portfolio data for testing."""
        data = pd.DataFrame({
            'close': [100.0, 101.0, 102.0],
            'high': [101.0, 102.0, 103.0],
            'low': [99.0, 100.0, 101.0],
            'volume': [1000, 1100, 1200]
        })
        return {'RELIANCE': data, 'HDFC': data}

    def test_parse_response_with_ai_thresholds(self):
        """Test parsing response where AI provides custom thresholds."""
        portfolio_data = self.create_sample_portfolio_data()
        context = {'current_positions': ['RELIANCE']}

        response = """{
            "market_analysis": "Bullish market",
            "decisions": {
                "RELIANCE": {
                    "signal": "HOLD",
                    "confidence": 0.75,
                    "reasoning": "Strong position",
                    "entry_price": null,
                    "stop_loss": null,
                    "take_profit": null,
                    "emergency_thresholds": {
                        "stop_loss_pct": -5.0,
                        "take_profit_pct": 7.0,
                        "recheck_trigger_pct": 2.5,
                        "comment": "Large position monitoring"
                    }
                },
                "HDFC": {
                    "signal": "BUY",
                    "confidence": 0.80,
                    "reasoning": "Good entry point",
                    "entry_price": 102.0,
                    "stop_loss": 98.0,
                    "take_profit": 108.0,
                    "emergency_thresholds": {
                        "stop_loss_pct": -2.5,
                        "take_profit_pct": null,
                        "comment": "New position"
                    }
                }
            }
        }"""

        result = PromptBuilder.parse_portfolio_response(response, portfolio_data, context)

        # Check RELIANCE (owned position with AI thresholds)
        reliance = result['decisions']['RELIANCE']
        assert reliance['emergency_thresholds']['stop_loss_pct'] == -5.0
        assert reliance['emergency_thresholds']['take_profit_pct'] == 7.0
        assert reliance['emergency_thresholds']['recheck_trigger_pct'] == 2.5
        assert reliance['emergency_thresholds']['comment'] == 'Large position monitoring'

        # Check HDFC (BUY signal with partial AI thresholds)
        hdfc = result['decisions']['HDFC']
        assert hdfc['emergency_thresholds']['stop_loss_pct'] == -2.5
        assert hdfc['emergency_thresholds']['take_profit_pct'] == 4.0  # Default
        assert hdfc['emergency_thresholds']['recheck_trigger_pct'] == 2.0  # Default
        assert hdfc['emergency_thresholds']['comment'] == 'New position'

    def test_parse_response_missing_emergency_thresholds(self):
        """Test parsing response where AI doesn't provide emergency thresholds."""
        portfolio_data = self.create_sample_portfolio_data()
        context = {'current_positions': ['RELIANCE']}

        response = """{
            "market_analysis": "Neutral market",
            "decisions": {
                "RELIANCE": {
                    "signal": "HOLD",
                    "confidence": 0.60,
                    "reasoning": "Wait and see",
                    "entry_price": null,
                    "stop_loss": null,
                    "take_profit": null
                },
                "HDFC": {
                    "signal": "HOLD",
                    "confidence": 0.50,
                    "reasoning": "No clear signal",
                    "entry_price": null,
                    "stop_loss": null,
                    "take_profit": null
                }
            }
        }"""

        result = PromptBuilder.parse_portfolio_response(response, portfolio_data, context)

        # RELIANCE is owned, should get default thresholds
        reliance = result['decisions']['RELIANCE']
        assert reliance['emergency_thresholds']['stop_loss_pct'] == -3.5
        assert reliance['emergency_thresholds']['take_profit_pct'] == 4.0
        assert reliance['emergency_thresholds']['recheck_trigger_pct'] == 2.0
        assert reliance['emergency_thresholds']['comment'] == 'Standard monitoring'

        # HDFC is unowned HOLD, should not be monitored
        hdfc = result['decisions']['HDFC']
        assert hdfc['emergency_thresholds']['stop_loss_pct'] is None
        assert hdfc['emergency_thresholds']['take_profit_pct'] is None
        assert hdfc['emergency_thresholds']['recheck_trigger_pct'] is None
        assert hdfc['emergency_thresholds']['comment'] is None

    def test_parse_response_missing_symbol(self):
        """Test parsing when AI doesn't provide decision for a symbol."""
        portfolio_data = self.create_sample_portfolio_data()
        context = {'current_positions': ['RELIANCE']}

        response = """{
            "market_analysis": "Mixed signals",
            "decisions": {
                "HDFC": {
                    "signal": "SELL",
                    "confidence": 0.85,
                    "reasoning": "Take profits",
                    "entry_price": 102.0,
                    "stop_loss": null,
                    "take_profit": null
                }
            }
        }"""

        result = PromptBuilder.parse_portfolio_response(response, portfolio_data, context)

        # RELIANCE missing from AI response but is owned, should get defaults
        reliance = result['decisions']['RELIANCE']
        assert reliance['signal'] == 'HOLD'
        assert reliance['confidence'] == 0.3
        assert reliance['emergency_thresholds']['stop_loss_pct'] == -3.5
        assert reliance['emergency_thresholds']['take_profit_pct'] == 4.0
        assert reliance['emergency_thresholds']['comment'] == 'Standard monitoring'

    def test_parse_malformed_emergency_thresholds(self):
        """Test handling of malformed emergency_thresholds field."""
        portfolio_data = self.create_sample_portfolio_data()
        context = {'current_positions': []}

        response = """{
            "market_analysis": "Testing malformed data",
            "decisions": {
                "RELIANCE": {
                    "signal": "BUY",
                    "confidence": 0.70,
                    "reasoning": "Good opportunity",
                    "entry_price": 100.0,
                    "emergency_thresholds": "not_a_dict"
                }
            }
        }"""

        result = PromptBuilder.parse_portfolio_response(response, portfolio_data, context)

        # Should handle malformed data gracefully
        reliance = result['decisions']['RELIANCE']
        assert reliance['signal'] == 'BUY'
        assert reliance['emergency_thresholds']['stop_loss_pct'] == -3.5  # Default
        assert reliance['emergency_thresholds']['take_profit_pct'] == 4.0  # Default


class TestPromptBuilderSafeFormat:
    """Test safe formatting utility method."""

    def test_safe_format_valid_numbers(self):
        """Test formatting valid numbers."""
        assert PromptBuilder.safe_format(123.456, decimals=2) == "123.46"
        assert PromptBuilder.safe_format(0.0) == "0.00"
        assert PromptBuilder.safe_format(-45.67, decimals=1) == "-45.7"

    def test_safe_format_none_values(self):
        """Test formatting None values."""
        assert PromptBuilder.safe_format(None) == "0.00"
        assert PromptBuilder.safe_format(None, default=100, decimals=1) == "100.0"

    def test_safe_format_pandas_na(self):
        """Test formatting pandas NA values."""
        assert PromptBuilder.safe_format(pd.NA) == "0.00"
        assert PromptBuilder.safe_format(pd.NaT, default=50) == "50.00"

    def test_safe_format_string_numbers(self):
        """Test formatting string numbers."""
        assert PromptBuilder.safe_format("123.45") == "123.45"
        assert PromptBuilder.safe_format("0") == "0.00"

    def test_safe_format_invalid_values(self):
        """Test formatting invalid values."""
        assert PromptBuilder.safe_format("not_a_number") == "0.00"
        assert PromptBuilder.safe_format("invalid", default=99) == "99.00"
        assert PromptBuilder.safe_format([], default=42) == "42.00"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])