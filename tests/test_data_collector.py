#!/usr/bin/env python3
"""
Test script for data_collector module
Run this to verify your setup is working correctly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_collector import DataCollector, MarketData
from src.config import SYMBOLS, is_market_hours
from datetime import datetime
import time


def test_single_symbol():
    """Test fetching data for a single symbol"""
    print("\n" + "="*50)
    print("TEST 1: Single Symbol Fetch")
    print("="*50)
    
    collector = DataCollector()
    
    try:
        # Test with first symbol
        symbol = SYMBOLS[0]
        print(f"\nFetching data for {symbol}...")
        
        success = collector.collect_and_store(symbol)
        
        if success:
            print(f"✅ Successfully collected data for {symbol}")
            
            # Check if data was saved
            recent_data = collector.db.get_recent_data(symbol, periods=1)
            if not recent_data.empty:
                latest = recent_data.iloc[-1]
                print(f"\nLatest data:")
                print(f"  Timestamp: {latest['timestamp']}")
                print(f"  Open:  ₹{latest['open']:.2f}")
                print(f"  High:  ₹{latest['high']:.2f}")
                print(f"  Low:   ₹{latest['low']:.2f}")
                print(f"  Close: ₹{latest['close']:.2f}")
                print(f"  Volume: {latest['volume']:,}")
        else:
            print(f"❌ Failed to collect data for {symbol}")
            
    finally:
        collector.close()


def test_all_symbols():
    """Test fetching data for all configured symbols"""
    print("\n" + "="*50)
    print("TEST 2: All Symbols Fetch")
    print("="*50)
    
    collector = DataCollector()
    
    try:
        print(f"\nFetching data for {len(SYMBOLS)} symbols...")
        print("This may take a minute...\n")
        
        results = collector.collect_all_symbols()
        
        # Display results
        success_count = sum(1 for v in results.values() if v)
        print(f"\nResults: {success_count}/{len(SYMBOLS)} successful")
        print("-"*30)
        
        for symbol, success in results.items():
            status = "✅" if success else "❌"
            print(f"{status} {symbol}")
            
    finally:
        collector.close()


def test_indicators():
    """Test indicator calculation"""
    print("\n" + "="*50)
    print("TEST 3: Indicator Calculation")
    print("="*50)
    
    collector = DataCollector()
    
    try:
        # Collect some data first
        symbol = "RELIANCE"
        print(f"\nCollecting historical data for {symbol}...")
        
        # Try to collect multiple times to build history
        for i in range(3):
            collector.collect_and_store(symbol)
            if i < 2:
                print(f"Waiting 10 seconds before next collection...")
                time.sleep(10)
        
        # Check indicators
        query = '''
            SELECT * FROM indicators 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        '''
        
        result = collector.db.conn.execute(query, (symbol,)).fetchone()
        
        if result:
            print(f"\nCalculated indicators for {symbol}:")
            print(f"  SMA 20: {result['sma_20']:.2f}" if result['sma_20'] else "  SMA 20: Not enough data")
            print(f"  RSI 14: {result['rsi_14']:.2f}" if result['rsi_14'] else "  RSI 14: Not enough data")
            print(f"  MACD: {result['macd']:.4f}" if result['macd'] else "  MACD: Not enough data")
        else:
            print("No indicators calculated yet (need more historical data)")
            
    finally:
        collector.close()


def test_cache():
    """Test caching functionality"""
    print("\n" + "="*50)
    print("TEST 4: Cache Performance")
    print("="*50)
    
    collector = DataCollector()
    
    try:
        symbol = SYMBOLS[0]
        
        # First fetch (should hit API)
        print(f"\nFirst fetch for {symbol} (should use API)...")
        start = time.time()
        collector.collect_and_store(symbol)
        api_time = time.time() - start
        
        # Second fetch (should hit cache)
        print(f"Second fetch for {symbol} (should use cache)...")
        start = time.time()
        collector.collect_and_store(symbol)
        cache_time = time.time() - start
        
        print(f"\nPerformance comparison:")
        print(f"  API fetch time: {api_time:.3f}s")
        print(f"  Cache fetch time: {cache_time:.3f}s")
        print(f"  Speed improvement: {api_time/cache_time:.1f}x")
        
        # Check stats
        print(f"\nCache statistics:")
        print(f"  Cache hits: {collector.stats['cache_hits']}")
        print(f"  API calls: {sum(collector.stats['api_calls'].values())}")
        
    finally:
        collector.close()


def check_market_status():
    """Check if market is open"""
    print("\n" + "="*50)
    print("MARKET STATUS CHECK")
    print("="*50)
    
    if is_market_hours():
        print("✅ Market is OPEN - Data collection active")
    else:
        print("❌ Market is CLOSED")
        print("   Data collection will run but with limited/delayed data")
        print("   Best results during market hours (9:15 AM - 3:30 PM IST)")
    
    print(f"\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Run all tests"""
    print("\n🧪 TRADING BOT DATA COLLECTOR TEST SUITE")
    print("="*60)
    
    # Check market status first
    check_market_status()
    
    # Ask user which test to run
    print("\nAvailable tests:")
    print("1. Test single symbol fetch")
    print("2. Test all symbols fetch")
    print("3. Test indicator calculation")
    print("4. Test cache performance")
    print("5. Run all tests")
    print("0. Exit")
    
    choice = input("\nSelect test to run (0-5): ").strip()
    
    if choice == "1":
        test_single_symbol()
    elif choice == "2":
        test_all_symbols()
    elif choice == "3":
        test_indicators()
    elif choice == "4":
        test_cache()
    elif choice == "5":
        test_single_symbol()
        test_cache()
        test_all_symbols()
    elif choice == "0":
        print("Exiting...")
    else:
        print("Invalid choice!")
    
    print("\n✅ Testing completed!")
    print("Check logs in: data/logs/data_collector.log")


if __name__ == "__main__":
    main()
