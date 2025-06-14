#!/usr/bin/env python3
"""
Setup verification script for trading bot project.
Run this to ensure all dependencies are properly installed.
"""

import sys
import os
from datetime import datetime

def check_python_version():
    """Check if Python version is 3.9+"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print("❌ Python 3.9+ required")
        return False
    print("✅ Python version OK")
    return True

def check_imports():
    """Check if all required packages can be imported"""
    packages = {
        'pandas': 'Data manipulation',
        'numpy': 'Numerical computing',
        'yfinance': 'Yahoo Finance data',
        'anthropic': 'Claude API',
        'dotenv': 'Environment variables',
        'schedule': 'Task scheduling',
        'pytz': 'Timezone handling',
        'pytest': 'Testing framework'
    }
    
    print("\nChecking package imports:")
    all_good = True
    
    for package, description in packages.items():
        try:
            if package == 'dotenv':
                import dotenv
            else:
                __import__(package)
            print(f"✅ {package:<12} - {description}")
        except ImportError:
            print(f"❌ {package:<12} - {description} (MISSING)")
            all_good = False
    
    return all_good

def check_environment():
    """Check if environment variables are set"""
    print("\nChecking environment:")
    
    # Check if .env exists
    if os.path.exists('.env'):
        print("✅ .env file exists")
        
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Check critical variables
        api_key = os.getenv('ANTHROPIC_API_KEY', '')
        if api_key and api_key != 'your-claude-api-key-here':
            print("✅ ANTHROPIC_API_KEY is set")
        else:
            print("❌ ANTHROPIC_API_KEY not configured in .env")
            return False
    else:
        print("❌ .env file not found")
        return False
    
    return True

def check_directory_structure():
    """Check if all required directories exist"""
    print("\nChecking directory structure:")
    
    directories = [
        'src',
        'src/utils',
        'data',
        'data/historical',
        'data/live',
        'data/logs',
        'docs',
        'strategies',
        'tests'
    ]
    
    all_good = True
    for directory in directories:
        if os.path.exists(directory):
            print(f"✅ {directory}")
        else:
            print(f"❌ {directory} (MISSING)")
            all_good = False
    
    return all_good

def test_yahoo_finance():
    """Test Yahoo Finance connection"""
    print("\nTesting Yahoo Finance connection:")
    try:
        import yfinance as yf
        
        # Test with Reliance stock
        ticker = yf.Ticker("RELIANCE.NS")
        data = ticker.history(period="1d")
        
        if not data.empty:
            latest_price = data['Close'].iloc[-1]
            print(f"✅ Yahoo Finance working - RELIANCE.NS: ₹{latest_price:.2f}")
            return True
        else:
            print("❌ Yahoo Finance returned no data")
            return False
    except Exception as e:
        print(f"❌ Yahoo Finance error: {str(e)}")
        return False

def main():
    """Run all checks"""
    print("=" * 50)
    print("Trading Bot Setup Verification")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Package Imports", check_imports),
        ("Environment Setup", check_environment),
        ("Directory Structure", check_directory_structure),
        ("Yahoo Finance API", test_yahoo_finance)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error during {name}: {str(e)}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:<20} {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All checks passed! Your setup is ready.")
        print("\nNext steps:")
        print("1. Create src/config.py")
        print("2. Create src/data_collector.py")
        print("3. Test data collection with: python src/data_collector.py")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("- Install missing packages: pip install -r requirements.txt")
        print("- Create .env file: cp .env.template .env")
        print("- Add your Anthropic API key to .env")
    
    print("=" * 50)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
