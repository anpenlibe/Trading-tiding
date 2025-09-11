#!/usr/bin/env python3
"""Test data collection fixes."""

from src.data_collector import DataCollector
from src.data_sources import MockAPI
import time

def test_mock_api():
    """Test MockAPI timestamp format."""
    print("Testing MockAPI...")
    mock = MockAPI()
    data = mock.fetch_ohlc("RELIANCE")
    
    if data:
        print(f"✅ MockAPI working")
        print(f"   Timestamp: {data.timestamp}")
        print(f"   Type: {type(data.timestamp)}")
        print(f"   Price: {data.close}")
    else:
        print("❌ MockAPI failed")
    
    return data is not None

def test_data_collection():
    """Test full data collection."""
    print("\nTesting DataCollector...")
    collector = DataCollector()
    
    # Test collection for one symbol
    success = collector.collect_and_store("RELIANCE")
    
    if success:
        print("✅ Data collection working")
        
        # Verify data in database
        recent = collector.get_recent_data("RELIANCE", 1)
        if not recent.empty:
            print(f"✅ Data stored in database")
            print(f"   Last price: {recent.iloc[-1]['close']}")
            print(f"   Timestamp: {recent.iloc[-1]['timestamp']}")
    else:
        print("❌ Data collection failed")
    
    return success

def test_multiple_symbols():
    """Test multiple symbol collection."""
    print("\nTesting multiple symbols...")
    collector = DataCollector()
    
    symbols = ["RELIANCE", "SBIN", "INFY"]
    success_count = 0
    
    for symbol in symbols:
        if collector.collect_and_store(symbol):
            success_count += 1
            print(f"✅ {symbol} collected")
        else:
            print(f"❌ {symbol} failed")
        time.sleep(0.5)  # Small delay
    
    print(f"\nSuccess rate: {success_count}/{len(symbols)}")
    return success_count == len(symbols)

if __name__ == "__main__":
    print("="*60)
    print("DATA COLLECTION FIX TEST")
    print("="*60)
    
    all_pass = True
    all_pass &= test_mock_api()
    all_pass &= test_data_collection()
    all_pass &= test_multiple_symbols()
    
    print("="*60)
    if all_pass:
        print("✅ ALL TESTS PASS - Data collection fixed!")
    else:
        print("❌ Some tests failed - check logs")