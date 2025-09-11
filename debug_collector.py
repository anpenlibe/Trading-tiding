#!/usr/bin/env python3
"""Debug data collector issues."""

from src.data_collector import DataCollector
from src.data_sources import MockAPI
from src.data.database import DatabaseManager
from src.indicator_engine import calculate_all_indicators
import os

def test_collector_step_by_step():
    """Test data collector step by step."""
    print("Testing data collector step by step...")
    
    # Delete existing database to start fresh
    db_path = "/home/anpenlibe/trading-tiding/data/market_data.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing database")
    
    # Create components individually
    print("1. Creating MockAPI...")
    mock = MockAPI()
    
    print("2. Creating DatabaseManager...")
    db = DatabaseManager(db_path)
    
    print("3. Fetching mock data...")
    data = mock.fetch_ohlc("RELIANCE")
    print(f"   Data: {data}")
    
    print("4. Saving data directly to database...")
    try:
        success = db.save_market_data(data)
        print(f"   Save success: {success}")
    except Exception as e:
        print(f"   Save failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("5. Retrieving data from database...")
    try:
        recent = db.get_recent_data("RELIANCE", 1)
        print(f"   Retrieved: {not recent.empty}")
        if not recent.empty:
            print(f"   Data shape: {recent.shape}")
            print(f"   Columns: {recent.columns.tolist()}")
            print(f"   Timestamp type: {type(recent.iloc[0]['timestamp'])}")
    except Exception as e:
        print(f"   Retrieve failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("6. Testing indicator calculation...")
    try:
        # Add more dummy data for indicators
        for i in range(25):  # Need enough data for indicators
            dummy_data = mock.fetch_ohlc("RELIANCE")
            db.save_market_data(dummy_data)
        
        recent_full = db.get_recent_data("RELIANCE", 25)
        print(f"   Data for indicators: {recent_full.shape}")
        
        if len(recent_full) >= 20:
            indicators = calculate_all_indicators(recent_full)
            print(f"   Indicators calculated: {len(indicators)}")
            print(f"   Sample indicators: {list(indicators.keys())[:5]}")
        else:
            print(f"   Not enough data for indicators: {len(recent_full)}")
    except Exception as e:
        print(f"   Indicator calculation failed: {e}")
        import traceback
        traceback.print_exc()
    
    db.close()

def test_collector_directly():
    """Test DataCollector class directly."""
    print("\nTesting DataCollector directly...")
    
    # Delete existing database to start fresh
    db_path = "/home/anpenlibe/trading-tiding/data/market_data.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing database")
    
    try:
        collector = DataCollector()
        print("DataCollector initialized successfully")
        
        print("Testing collect_and_store...")
        success = collector.collect_and_store("RELIANCE")
        print(f"Collection success: {success}")
        
        if success:
            print("Verifying stored data...")
            recent = collector.get_recent_data("RELIANCE", 1)
            if not recent.empty:
                print(f"✅ Data verification successful")
                print(f"   Price: {recent.iloc[-1]['close']}")
            else:
                print("❌ No data found after collection")
        
    except Exception as e:
        print(f"DataCollector failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("="*60)
    print("DATA COLLECTOR DEBUG TEST")
    print("="*60)
    
    test_collector_step_by_step()
    test_collector_directly()