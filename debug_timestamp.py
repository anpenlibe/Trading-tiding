#!/usr/bin/env python3
"""Debug timestamp issues."""

from src.data_sources import MockAPI
from src.data.database import DatabaseManager
from src.interfaces import MarketData
from datetime import datetime
import os

def test_mock_data_creation():
    """Test mock data creation."""
    print("Testing mock data creation...")
    mock = MockAPI()
    data = mock.fetch_ohlc("RELIANCE")
    
    print(f"Mock data timestamp: {data.timestamp}")
    print(f"Mock data type: {type(data.timestamp)}")
    print(f"Has timezone: {hasattr(data.timestamp, 'tzinfo') and data.timestamp.tzinfo is not None}")
    
    return data

def test_database_save():
    """Test database save directly."""
    print("\nTesting database save...")
    
    # Delete existing database to start fresh
    db_path = "/home/anpenlibe/trading-tiding/data/market_data.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing database")
    
    # Create new database
    db = DatabaseManager(db_path)
    
    # Create test data with naive timestamp
    test_data = MarketData(
        symbol="TEST",
        timestamp=datetime.now().replace(microsecond=0),
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=10000,
        source="test"
    )
    
    print(f"Test data timestamp: {test_data.timestamp}")
    print(f"Test data type: {type(test_data.timestamp)}")
    print(f"Has timezone: {hasattr(test_data.timestamp, 'tzinfo') and test_data.timestamp.tzinfo is not None}")
    
    # Try to save
    try:
        success = db.save_market_data(test_data)
        print(f"Save success: {success}")
        
        if success:
            # Try to retrieve
            recent = db.get_recent_data("TEST", 1)
            print(f"Retrieved data: {not recent.empty}")
            if not recent.empty:
                print(f"Retrieved timestamp: {recent.iloc[0]['timestamp']}")
                print(f"Retrieved timestamp type: {type(recent.iloc[0]['timestamp'])}")
        
    except Exception as e:
        print(f"Error saving: {e}")
        import traceback
        traceback.print_exc()
    
    db.close()

def test_mock_to_database():
    """Test full flow from mock to database."""
    print("\nTesting mock to database flow...")
    
    # Delete existing database to start fresh
    db_path = "/home/anpenlibe/trading-tiding/data/market_data.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing database")
    
    # Create components
    mock = MockAPI()
    db = DatabaseManager(db_path)
    
    # Get mock data
    data = mock.fetch_ohlc("RELIANCE")
    print(f"Mock data: {data}")
    
    # Try to save
    try:
        success = db.save_market_data(data)
        print(f"Save success: {success}")
        
    except Exception as e:
        print(f"Error in mock to database: {e}")
        import traceback
        traceback.print_exc()
    
    db.close()

if __name__ == "__main__":
    print("="*60)
    print("TIMESTAMP DEBUG TEST")
    print("="*60)
    
    test_mock_data_creation()
    test_database_save() 
    test_mock_to_database()