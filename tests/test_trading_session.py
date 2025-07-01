#!/usr/bin/env python3
"""
Module: test_trading_session.py
Purpose: Complete system test without requiring Claude API credits
Author: Trading Bot Developer
Created: 2025-07-01

This script tests the entire trading system integration:
- Data collection and indicators
- Risk management calculations  
- Paper trading execution
- Performance tracking
- All without requiring Claude API calls

Perfect for validating system before live trading!
"""

import os
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import SYMBOLS, INITIAL_CAPITAL
from src.data_collector import DataCollector
from src.risk_manager import SimpleRiskManager
from src.paper_trader import PaperTrader
from src.indicator_engine import calculate_all_indicators
from src.stock_registry import get_stock_registry


class MockSignalGenerator:
    """Generate realistic trading signals for testing"""
    
    def __init__(self):
        self.signal_count = 0
        self.last_signals = {}
    
    def generate_signal(self, symbol: str, market_data: pd.DataFrame, indicators: Dict) -> Dict:
        """Generate a realistic trading signal based on indicators"""
        self.signal_count += 1
        
        current_price = float(market_data['close'].iloc[-1])
        rsi = indicators.get('rsi_14', 50)
        sma_20 = indicators.get('sma_20', current_price)
        sma_50 = indicators.get('sma_50', current_price)
        
        # Simple but realistic signal logic
        signal = "HOLD"
        confidence = 0.5
        reasoning = "Neutral market conditions"
        
        # Bullish conditions
        if current_price > sma_20 > sma_50 and rsi < 70:
            signal = "BUY"
            confidence = 0.7
            reasoning = f"Bullish: Price above SMAs, RSI={rsi:.1f} not overbought"
        
        # Bearish conditions  
        elif current_price < sma_20 and rsi > 30:
            signal = "SELL"
            confidence = 0.6
            reasoning = f"Bearish: Price below SMA20, RSI={rsi:.1f}"
        
        # Oversold bounce
        elif rsi < 30:
            signal = "BUY"
            confidence = 0.8
            reasoning = f"Oversold bounce opportunity, RSI={rsi:.1f}"
        
        # Overbought sell
        elif rsi > 70:
            signal = "SELL"
            confidence = 0.7
            reasoning = f"Overbought conditions, RSI={rsi:.1f}"
        
        return {
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'reasoning': reasoning,
            'entry_price': current_price,
            'stop_loss': current_price * (0.985 if signal == 'BUY' else 1.015),
            'target': current_price * (1.03 if signal == 'BUY' else 0.97)
        }


class TradingSystemTester:
    """Complete trading system tester"""
    
    def __init__(self):
        print("🤖 Trading System Integration Test")
        print("=" * 50)
        
        # Initialize components
        self.data_collector = DataCollector()
        self.risk_manager = SimpleRiskManager()
        self.paper_trader = PaperTrader(INITIAL_CAPITAL)
        self.signal_generator = MockSignalGenerator()
        self.stock_registry = get_stock_registry()
        
        # Test statistics
        self.test_stats = {
            'symbols_processed': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'validation_failures': 0,
            'start_time': datetime.now()
        }
        
        print("✅ All components initialized successfully")
    
    def test_data_collection(self) -> bool:
        """Test data collection and indicator calculation"""
        print("\n📊 Testing Data Collection & Indicators...")
        
        success_count = 0
        for symbol in SYMBOLS[:3]:  # Test first 3 symbols
            try:
                # Get market data
                market_data = self.data_collector.get_recent_data(symbol, periods=50)
                
                if not market_data.empty:
                    # Add symbol column
                    market_data['symbol'] = symbol
                    
                    # Calculate indicators
                    indicators = calculate_all_indicators(market_data)
                    
                    if indicators:
                        print(f"  ✅ {symbol}: {len(market_data)} records, {len(indicators)} indicators")
                        success_count += 1
                    else:
                        print(f"  ❌ {symbol}: No indicators calculated")
                else:
                    print(f"  ❌ {symbol}: No market data available")
                    
            except Exception as e:
                print(f"  ❌ {symbol}: Error - {e}")
        
        success_rate = success_count / len(SYMBOLS[:3]) * 100
        print(f"📈 Data Collection Success Rate: {success_rate:.1f}%")
        return success_rate > 50
    
    def test_signal_generation(self) -> List[Dict]:
        """Test signal generation for all symbols"""
        print("\n🧠 Testing Signal Generation...")
        
        signals = []
        for symbol in SYMBOLS[:5]:  # Test first 5 symbols
            try:
                # Get market data and indicators
                market_data = self.data_collector.get_recent_data(symbol, periods=50)
                if market_data.empty:
                    continue
                    
                market_data['symbol'] = symbol
                indicators = calculate_all_indicators(market_data)
                
                if not indicators:
                    continue
                
                # Generate signal
                signal = self.signal_generator.generate_signal(symbol, market_data, indicators)
                signals.append(signal)
                
                print(f"  📊 {symbol}: {signal['signal']} (confidence: {signal['confidence']:.2f})")
                print(f"     Reasoning: {signal['reasoning']}")
                
                self.test_stats['signals_generated'] += 1
                
            except Exception as e:
                print(f"  ❌ {symbol}: Signal generation error - {e}")
        
        print(f"🎯 Generated {len(signals)} trading signals")
        return signals
    
    def test_risk_management(self, signals: List[Dict]) -> List[Dict]:
        """Test risk management validation and position sizing"""
        print("\n⚠️  Testing Risk Management...")
        
        validated_signals = []
        account_info = self.paper_trader.get_account_info()
        current_positions = self.paper_trader.get_positions()
        
        for signal in signals:
            try:
                # Add capital info for validation
                signal['available_capital'] = account_info['available_capital']
                
                # Validate trade
                is_valid, rejection_reason = self.risk_manager.validate_trade(signal, current_positions)
                
                if is_valid:
                    # Calculate risk parameters
                    risk_params = self.risk_manager.calculate_risk_parameters(
                        symbol=signal['symbol'],
                        signal_type=signal['signal'],
                        entry_price=signal['entry_price'],
                        capital=account_info['available_capital'],
                        stop_loss=signal.get('stop_loss'),
                        target=signal.get('target')
                    )
                    
                    # Update signal with risk calculations
                    signal.update({
                        'position_size': risk_params.position_size,
                        'risk_amount': risk_params.risk_amount,
                        'total_cost': risk_params.total_cost,
                        'risk_reward_ratio': risk_params.risk_reward_ratio
                    })
                    
                    validated_signals.append(signal)
                    
                    print(f"  ✅ {signal['symbol']}: Position size {risk_params.position_size}, "
                          f"Risk ₹{risk_params.risk_amount:.0f}, R:R {risk_params.risk_reward_ratio:.1f}")
                else:
                    print(f"  ❌ {signal['symbol']}: {rejection_reason}")
                    self.test_stats['validation_failures'] += 1
                    
            except Exception as e:
                print(f"  ❌ {signal['symbol']}: Risk calculation error - {e}")
        
        print(f"✅ Risk Management: {len(validated_signals)}/{len(signals)} signals approved")
        return validated_signals
    
    def test_trade_execution(self, validated_signals: List[Dict]) -> List[Dict]:
        """Test paper trade execution"""
        print("\n💰 Testing Trade Execution...")
        
        executed_trades = []
        
        for signal in validated_signals:
            if signal['signal'] == 'HOLD':
                continue
                
            try:
                # Execute trade
                result = self.paper_trader.execute_trade(signal, signal['entry_price'])
                
                if result.get('status') == 'EXECUTED':
                    executed_trades.append({
                        'symbol': signal['symbol'],
                        'action': signal['signal'],
                        'quantity': signal['position_size'],
                        'price': signal['entry_price'],
                        'result': result
                    })
                    
                    print(f"  ✅ {signal['symbol']}: {signal['signal']} {signal['position_size']} @ ₹{signal['entry_price']:.2f}")
                    self.test_stats['trades_executed'] += 1
                else:
                    print(f"  ❌ {signal['symbol']}: {result.get('reason', 'Unknown error')}")
                    
            except Exception as e:
                print(f"  ❌ {signal['symbol']}: Execution error - {e}")
        
        print(f"🎯 Executed {len(executed_trades)} trades")
        return executed_trades
    
    def test_performance_tracking(self) -> Dict:
        """Test performance tracking and reporting"""
        print("\n📈 Testing Performance Tracking...")
        
        # Get account performance
        account_info = self.paper_trader.get_account_info()
        positions = self.paper_trader.get_positions()
        
        print(f"  💰 Current Capital: ₹{account_info['current_capital']:.2f}")
        print(f"  📊 Available Capital: ₹{account_info['available_capital']:.2f}")
        print(f"  📈 Total Return: {account_info['total_return']:+.2f}%")
        print(f"  🏢 Open Positions: {len(positions)}")
        print(f"  📋 Total Trades: {account_info['total_trades']}")
        
        if positions:
            print(f"  📊 Position Details:")
            for symbol, pos in positions.items():
                print(f"    {symbol}: {pos['quantity']} shares @ ₹{pos['entry_price']:.2f} "
                      f"(P&L: {pos.get('pnl_percent', 0):+.1f}%)")
        
        # Generate performance report
        try:
            performance_report = self.paper_trader.generate_performance_report()
            print(f"  📊 Max Drawdown: {performance_report['max_drawdown']:.2f}%")
            print(f"  📊 Profit Factor: {performance_report.get('profit_factor', 'N/A')}")
        except Exception as e:
            print(f"  ⚠️  Performance report error: {e}")
        
        return account_info
    
    def run_complete_test(self):
        """Run complete system integration test"""
        print(f"\n🚀 Starting Complete System Test")
        print(f"📊 Testing with symbols: {', '.join(SYMBOLS[:5])}")
        print(f"💰 Initial capital: ₹{INITIAL_CAPITAL:,.0f}")
        
        try:
            # Step 1: Test data collection
            data_success = self.test_data_collection()
            if not data_success:
                print("❌ Data collection test failed - stopping")
                return
            
            # Step 2: Test signal generation
            signals = self.test_signal_generation()
            if not signals:
                print("❌ No signals generated - stopping")
                return
            
            # Step 3: Test risk management
            validated_signals = self.test_risk_management(signals)
            
            # Step 4: Test trade execution  
            executed_trades = self.test_trade_execution(validated_signals)
            
            # Step 5: Test performance tracking
            final_performance = self.test_performance_tracking()
            
            # Generate final summary
            self.generate_test_summary(final_performance)
            
        except Exception as e:
            print(f"❌ Critical test error: {e}")
        finally:
            self.cleanup()
    
    def generate_test_summary(self, performance: Dict):
        """Generate comprehensive test summary"""
        duration = (datetime.now() - self.test_stats['start_time']).total_seconds()
        
        print("\n" + "=" * 60)
        print("🎯 INTEGRATION TEST SUMMARY")
        print("=" * 60)
        print(f"⏱️  Test Duration: {duration:.1f} seconds")
        print(f"📊 Symbols Processed: {len(SYMBOLS[:5])}")
        print(f"🎯 Signals Generated: {self.test_stats['signals_generated']}")
        print(f"💰 Trades Executed: {self.test_stats['trades_executed']}")
        print(f"❌ Validation Failures: {self.test_stats['validation_failures']}")
        
        print(f"\n💰 FINANCIAL RESULTS:")
        print(f"   Initial Capital: ₹{INITIAL_CAPITAL:,.0f}")
        print(f"   Final Capital: ₹{performance['current_capital']:,.2f}")
        print(f"   Total Return: {performance['total_return']:+.2f}%")
        print(f"   Open Positions: {performance['open_positions']}")
        
        # Calculate success rates
        signal_rate = (self.test_stats['signals_generated'] / len(SYMBOLS[:5]) * 100) if SYMBOLS else 0
        execution_rate = (self.test_stats['trades_executed'] / max(1, self.test_stats['signals_generated']) * 100)
        
        print(f"\n📈 SUCCESS RATES:")
        print(f"   Signal Generation: {signal_rate:.1f}%")
        print(f"   Trade Execution: {execution_rate:.1f}%")
        
        # Overall assessment
        if (self.test_stats['trades_executed'] > 0 and 
            self.test_stats['validation_failures'] < self.test_stats['signals_generated']):
            print(f"\n✅ OVERALL: INTEGRATION TEST SUCCESSFUL!")
            print(f"   System is ready for live trading with API credits")
        else:
            print(f"\n⚠️  OVERALL: PARTIAL SUCCESS")
            print(f"   Some components may need attention")
        
        print("=" * 60)
    
    def cleanup(self):
        """Cleanup resources"""
        if hasattr(self.data_collector, 'close'):
            self.data_collector.close()


def main():
    """Run the complete system test"""
    tester = TradingSystemTester()
    tester.run_complete_test()


if __name__ == "__main__":
    main()
