#!/usr/bin/env python3
"""
System Check Script - Run this before starting the trading bot
Checks all components, APIs, and configurations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
from datetime import datetime
from colorama import init, Fore, Style
init(autoreset=True)


def print_header(text):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")


def print_check(item, status, details=""):
    if status:
        print(f"{Fore.GREEN}✓ {item}{Style.RESET_ALL} {details}")
    else:
        print(f"{Fore.RED}✗ {item}{Style.RESET_ALL} {details}")


def check_imports():
    """Check if all modules can be imported"""
    print_header("1. CHECKING MODULE IMPORTS")
    
    modules = [
        ("Config", "src.config"),
        ("Interfaces", "src.interfaces"),
        ("Data Sources", "src.data_sources"),
        ("Data Collector", "src.data_collector"),
        ("AI Brain", "src.ai_brain"),
        ("AI Brain Optimized", "src.ai_brain_optimized"),
        ("Paper Trader", "src.paper_trader"),
        ("Risk Manager", "src.risk_manager"),
        ("Logger", "src.utils.logger")
    ]
    
    all_good = True
    for name, module in modules:
        try:
            __import__(module)
            print_check(name, True)
        except Exception as e:
            print_check(name, False, f"- {str(e)}")
            all_good = False
    
    return all_good


def check_configuration():
    """Check configuration values"""
    print_header("2. CHECKING CONFIGURATION")
    
    try:
        from src.config import (
            ANTHROPIC_API_KEY, INITIAL_CAPITAL, SYMBOLS,
            MARKET_OPEN, MARKET_CLOSE, is_market_hours
        )
        
        # Check API key
        api_key_valid = ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-claude-api-key-here"
        print_check("Anthropic API Key", api_key_valid, 
                   "- ✓ Configured" if api_key_valid else "- ❌ NOT CONFIGURED")
        
        # Check capital
        print_check("Initial Capital", True, f"- ₹{INITIAL_CAPITAL:,}")
        
        # Check symbols
        print_check("Trading Symbols", True, f"- {len(SYMBOLS)} symbols configured")
        
        # Check market hours
        print_check("Market Hours", True, f"- {MARKET_OPEN} to {MARKET_CLOSE}")
        
        # Check if market is open
        market_open = is_market_hours()
        current_time = datetime.now().strftime("%H:%M")
        print_check("Market Status", market_open, 
                   f"- {'OPEN' if market_open else 'CLOSED'} (Current: {current_time})")
        
        return api_key_valid
        
    except Exception as e:
        print(f"{Fore.RED}Configuration error: {e}{Style.RESET_ALL}")
        return False


def check_data_sources():
    """Check available data sources"""
    print_header("3. CHECKING DATA SOURCES")
    
    try:
        from src.data_sources import DhanAPI, YFinanceAPI, TwelveDataAPI, MockAPI
        from src.config import DHAN_API_KEY, TWELVE_DATA_API_KEY
        
        # Check each API
        apis = [
            ("Dhan API", DhanAPI(), DHAN_API_KEY),
            ("Twelve Data", TwelveDataAPI(), TWELVE_DATA_API_KEY),
            ("yfinance", YFinanceAPI(), "No key needed"),
            ("Mock API", MockAPI(), "Always available")
        ]
        
        available_count = 0
        for name, api, key_info in apis:
            is_available = api.is_available()
            if is_available:
                available_count += 1
            print_check(name, is_available, f"- {key_info}")
        
        if available_count == 0:
            print(f"\n{Fore.YELLOW}⚠️  No real data sources available - will use mock data{Style.RESET_ALL}")
        
        return available_count > 0
        
    except Exception as e:
        print(f"{Fore.RED}Data source error: {e}{Style.RESET_ALL}")
        return False


def check_database():
    """Check database connectivity"""
    print_header("4. CHECKING DATABASE")
    
    try:
        from src.data_collector import DataCollector
        
        collector = DataCollector()
        
        # Check tables exist
        tables = ['price_data', 'indicators', 'daily_stats', 'data_quality_log']
        cursor = collector.db.conn.cursor()
        
        for table in tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            exists = cursor.fetchone() is not None
            print_check(f"Table: {table}", exists)
        
        # Check data count
        cursor.execute("SELECT COUNT(*) FROM price_data")
        count = cursor.fetchone()[0]
        print_check("Historical Data", True, f"- {count:,} records")
        
        collector.close()
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Database error: {e}{Style.RESET_ALL}")
        return False


def test_data_collection():
    """Test live data collection"""
    print_header("5. TESTING DATA COLLECTION")
    
    try:
        from src.data_collector import DataCollector
        from src.config import SYMBOLS
        
        collector = DataCollector()
        test_symbol = SYMBOLS[0]
        
        print(f"Testing with {test_symbol}...")
        
        # Try to fetch data
        start_time = time.time()
        success = collector.collect_and_store(test_symbol)
        duration = time.time() - start_time
        
        if success:
            print_check(f"Data Collection", True, f"- Fetched in {duration:.2f}s")
            
            # Check what we got
            recent_data = collector.db.get_recent_data(test_symbol, periods=1)
            if not recent_data.empty:
                latest = recent_data.iloc[-1]
                print(f"  Latest Price: ₹{latest['close']:.2f}")
                print(f"  Volume: {latest['volume']:,}")
                print(f"  Timestamp: {latest['timestamp']}")
        else:
            print_check("Data Collection", False, "- Failed to fetch data")
            print(f"{Fore.YELLOW}  This might be normal if market is closed{Style.RESET_ALL}")
        
        collector.close()
        return success
        
    except Exception as e:
        print(f"{Fore.RED}Collection error: {e}{Style.RESET_ALL}")
        return False


def test_ai_brain():
    """Test AI brain initialization"""
    print_header("6. TESTING AI BRAIN")
    
    try:
        from src.ai_brain_optimized import OptimizedClaudeAI
        from src.config import ANTHROPIC_API_KEY
        
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-claude-api-key-here":
            print_check("AI Brain", False, "- API key not configured")
            return False
        
        ai = OptimizedClaudeAI()
        print_check("AI Brain", True, "- Initialized successfully")
        print(f"  Model: {ai.model}")
        print(f"  Capital: ₹{ai.capital:,}")
        
        return True
        
    except Exception as e:
        print(f"{Fore.RED}AI Brain error: {e}{Style.RESET_ALL}")
        return False


def test_paper_trader():
    """Test paper trader initialization"""
    print_header("7. TESTING PAPER TRADER")
    
    try:
        from src.paper_trader import PaperTrader
        
        trader = PaperTrader()
        print_check("Paper Trader", True, f"- Capital: ₹{trader.initial_capital:,}")
        print_check("Risk Manager", hasattr(trader, 'risk_manager'), "- Integrated")
        
        return True
        
    except Exception as e:
        print(f"{Fore.RED}Paper Trader error: {e}{Style.RESET_ALL}")
        return False


def check_logs_directory():
    """Check if logs directory exists"""
    print_header("8. CHECKING LOGS")
    
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'logs')
    exists = os.path.exists(log_dir)
    
    if not exists:
        os.makedirs(log_dir, exist_ok=True)
        print_check("Logs Directory", True, "- Created")
    else:
        print_check("Logs Directory", True, "- Exists")
    
    return True


def main():
    """Run all checks"""
    print(f"\n{Fore.CYAN}🔍 TRADING BOT SYSTEM CHECK")
    print(f"{Fore.CYAN}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")
    
    checks = [
        ("Module Imports", check_imports),
        ("Configuration", check_configuration),
        ("Data Sources", check_data_sources),
        ("Database", check_database),
        ("Logs", check_logs_directory),
        ("Data Collection", test_data_collection),
        ("AI Brain", test_ai_brain),
        ("Paper Trader", test_paper_trader)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n{Fore.RED}Error in {name}: {e}{Style.RESET_ALL}")
            results.append((name, False))
    
    # Summary
    print_header("SYSTEM CHECK SUMMARY")
    
    all_passed = True
    for name, result in results:
        print_check(name, result)
        if not result:
            all_passed = False
    
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    if all_passed:
        print(f"{Fore.GREEN}✅ ALL CHECKS PASSED! System is ready to run.{Style.RESET_ALL}")
        print(f"\nTo start trading:")
        print(f"  {Fore.YELLOW}python trading_system.py{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ Some checks failed. Please fix the issues above.{Style.RESET_ALL}")
        
        # Common fixes
        print(f"\n{Fore.YELLOW}Common fixes:")
        print("1. Set ANTHROPIC_API_KEY in .env file")
        print("2. Run: export PYTHONPATH=\"${PYTHONPATH}:$(pwd)\"")
        print("3. Install missing packages: pip install -r requirements.txt")
        print("4. Run historical data collection if database is empty")
        print(f"{Style.RESET_ALL}")
    
    return all_passed


if __name__ == "__main__":
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    success = main()
    sys.exit(0 if success else 1)
