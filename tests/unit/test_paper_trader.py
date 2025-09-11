"""Unit tests for paper trader - FIXED to match actual implementation."""

import pytest
from src.core.paper_trader import PaperTrader
from src.interfaces import TradingSignal


class TestPaperTrader:
    """Test paper trading functionality."""
    
    def test_execute_simple_trade_buy(self, paper_trader):
        """Test executing a simple buy trade."""
        result = paper_trader.execute_simple_trade(
            symbol="TEST",
            action="BUY",
            price=100.0,
            quantity=10
        )
        
        # FIXED: Check actual return format - uses 'status' not 'success'
        assert result.get('status') == "EXECUTED"
        assert paper_trader.available_capital < 10000  # Capital reduced
        assert "TEST" in paper_trader.open_positions
    
    def test_execute_simple_trade_insufficient_capital(self, paper_trader):
        """Test trade rejection with insufficient capital."""
        result = paper_trader.execute_simple_trade(
            symbol="TEST",
            action="BUY",
            price=100.0,
            quantity=1000  # Would cost 100,000
        )
        
        # FIXED: Check actual return format
        assert result.get('status') == "REJECTED"
        assert 'capital' in result.get('reason', '').lower()
    
    def test_execute_sell_without_position(self, paper_trader):
        """Test selling without an open position."""
        result = paper_trader.execute_simple_trade(
            symbol="TEST",
            action="SELL",
            price=100.0,
            quantity=10
        )
        
        # FIXED: Check actual return format  
        assert result.get('status') == "REJECTED"
        assert 'position' in result.get('reason', '').lower()
    
    def test_performance_tracking(self, paper_trader):
        """Test performance metrics calculation."""
        # Execute a profitable trade
        buy_result = paper_trader.execute_simple_trade("TEST", "BUY", 100.0, 10)
        assert buy_result.get('status') == "EXECUTED"
        
        sell_result = paper_trader.execute_simple_trade("TEST", "SELL", 110.0, 10)
        assert sell_result.get('status') == "EXECUTED"
        
        performance = paper_trader.get_account_info()
        
        assert performance['total_trades'] > 0
        assert performance['current_capital'] > 10000  # Made profit
        assert performance['winning_trades'] == 1