#!/usr/bin/env python3
"""
Test script for AI Brain module
Run this to verify Claude integration is working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ai_brain import ClaudeAI, SimpleRuleBasedModel
from src.data_collector import DataCollector
from src.config import SYMBOLS
import pandas as pd
from datetime import datetime


def test_with_real_data():
    """Test AI Brain with real collected data"""
    print("\n🧠 TESTING AI BRAIN WITH REAL DATA")
    print("=" * 60)
    
    # Initialize components
    collector = DataCollector()
    ai_brain = ClaudeAI()
    rule_based = SimpleRuleBasedModel()
    
    try:
        # Get the first symbol
        symbol = SYMBOLS[0]
        print(f"\nTesting with {symbol}...")
        
        # Try to get recent data from database
        recent_data = collector.db.get_recent_data(symbol, periods=50)
        
        if recent_data.empty:
            print("❌ No historical data found. Collecting fresh data...")
            
            # Collect fresh data
            success = collector.collect_and_store(symbol)
            if not success:
                print("❌ Failed to collect data. Make sure market is open or use mock data.")
                return
            
            # Try again
            recent_data = collector.db.get_recent_data(symbol, periods=50)
        
        if not recent_data.empty:
            print(f"✅ Found {len(recent_data)} data points")
            
            # Get latest indicators
            query = """
                SELECT * FROM indicators 
                WHERE symbol = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            result = collector.db.conn.execute(query, (symbol,)).fetchone()
            
            if result:
                # Convert to dict
                indicators = {
                    'sma_20': result['sma_20'],
                    'sma_50': result['sma_50'],
                    'sma_200': result['sma_200'],
                    'rsi_14': result['rsi_14'],
                    'macd': result['macd'],
                    'macd_signal': result['macd_signal'],
                    'macd_histogram': result['macd_histogram'],
                    'volume_avg_20': result['volume_avg_20'],
                    'price_change_pct': result['price_change_pct']
                }
                
                # Add symbol column if not present
                if 'symbol' not in recent_data.columns:
                    recent_data['symbol'] = symbol
                
                print("\n📊 Current Market Status:")
                latest = recent_data.iloc[-1]
                print(f"Price: ₹{latest['close']:.2f}")
                print(f"Volume: {latest['volume']:,}")
                print(f"RSI: {indicators.get('rsi_14', 'N/A')}")
                print(f"SMA20: ₹{indicators.get('sma_20', 'N/A')}")
                
                # Test Claude AI
                print("\n🤖 Getting Claude's Analysis...")
                ai_decision = ai_brain.analyze(recent_data, indicators)
                
                print("\n=== CLAUDE AI DECISION ===")
                print(f"Signal: {ai_decision['signal']}")
                print(f"Confidence: {ai_decision['confidence']:.2%}")
                print(f"Reasoning: {ai_decision['reasoning']}")
                
                if ai_decision['signal'] != 'HOLD':
                    print(f"Entry: ₹{ai_decision.get('entry_price', 'N/A')}")
                    print(f"Stop Loss: ₹{ai_decision.get('stop_loss', 'N/A')}")
                    print(f"Target: ₹{ai_decision.get('target', 'N/A')}")
                    print(f"Position Size: {ai_decision.get('position_size', 'N/A')} shares")
                    print(f"Risk Amount: ₹{ai_decision.get('risk_amount', 'N/A')}")
                
                # Compare with rule-based
                print("\n📏 Rule-Based Analysis (for comparison)...")
                rule_decision = rule_based.analyze(recent_data, indicators)
                
                print("\n=== RULE-BASED DECISION ===")
                print(f"Signal: {rule_decision['signal']}")
                print(f"Confidence: {rule_decision['confidence']:.2%}")
                print(f"Reasoning: {rule_decision['reasoning']}")
                
            else:
                print("❌ No indicators calculated yet. Need more data points.")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        collector.close()


def test_all_symbols():
    """Test AI Brain on all configured symbols"""
    print("\n🔍 TESTING ALL SYMBOLS")
    print("=" * 60)
    
    collector = DataCollector()
    ai_brain = ClaudeAI()
    
    results = []
    
    try:
        for symbol in SYMBOLS[:3]:  # Test first 3 to save API calls
            print(f"\nAnalyzing {symbol}...")
            
            recent_data = collector.db.get_recent_data(symbol, periods=50)
            
            if not recent_data.empty:
                # Get indicators
                query = """
                    SELECT * FROM indicators 
                    WHERE symbol = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """
                result = collector.db.conn.execute(query, (symbol,)).fetchone()
                
                if result:
                    indicators = {key: result[key] for key in result.keys() 
                                if key not in ['id', 'symbol', 'timestamp', 'created_at']}
                    
                    if 'symbol' not in recent_data.columns:
                        recent_data['symbol'] = symbol
                    
                    decision = ai_brain.analyze(recent_data, indicators)
                    
                    results.append({
                        'symbol': symbol,
                        'price': recent_data['close'].iloc[-1],
                        'signal': decision['signal'],
                        'confidence': decision['confidence']
                    })
                    
                    print(f"✅ {symbol}: {decision['signal']} (confidence: {decision['confidence']:.2%})")
                else:
                    print(f"❌ {symbol}: No indicators available")
            else:
                print(f"❌ {symbol}: No data available")
        
        # Summary
        if results:
            print("\n📊 SUMMARY")
            print("=" * 60)
            df = pd.DataFrame(results)
            print(df.to_string(index=False))
            
            # Count signals
            buy_count = len(df[df['signal'] == 'BUY'])
            sell_count = len(df[df['signal'] == 'SELL'])
            hold_count = len(df[df['signal'] == 'HOLD'])
            
            print(f"\nSignal Distribution:")
            print(f"BUY: {buy_count}")
            print(f"SELL: {sell_count}")
            print(f"HOLD: {hold_count}")
            
    finally:
        collector.close()


def main():
    """Main test function"""
    print("\n🧪 AI BRAIN TEST SUITE")
    print("=" * 60)
    
    # Check if API key is configured
    from src.config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-claude-api-key-here":
        print("❌ Anthropic API key not configured!")
        print("Please set ANTHROPIC_API_KEY in your .env file")
        return
    
    print("✅ API key configured")
    
    # Menu
    print("\nSelect test:")
    print("1. Test with single symbol")
    print("2. Test multiple symbols")
    print("3. Exit")
    
    choice = input("\nChoice (1-3): ").strip()
    
    if choice == "1":
        test_with_real_data()
    elif choice == "2":
        test_all_symbols()
    else:
        print("Exiting...")


if __name__ == "__main__":
    main()
