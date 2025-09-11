#!/usr/bin/env python3
"""Comprehensive system health check."""

import sys
import os
import sqlite3
import argparse
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_imports() -> Tuple[bool, List[str]]:
    """Check all critical imports."""
    modules = [
        'src.core.ai_brain',
        'src.core.paper_trader', 
        'src.core.risk_manager',
        'src.data.database',
        'src.alerts.alert_engine',
        'src.utils.db_optimizer'
    ]
    
    failures = []
    for module in modules:
        try:
            __import__(module)
        except ImportError as e:
            failures.append(f"{module}: {e}")
    
    return len(failures) == 0, failures

def check_configuration() -> Tuple[bool, List[str]]:
    """Check configuration validity."""
    issues = []
    
    try:
        from src.data.config import ANTHROPIC_API_KEY, SYMBOLS
        
        if not ANTHROPIC_API_KEY:
            issues.append("ANTHROPIC_API_KEY not configured")
        
        if not SYMBOLS:
            issues.append("No trading symbols configured")
    except ImportError as e:
        issues.append(f"Config import failed: {e}")
    
    return len(issues) == 0, issues

def check_database() -> Tuple[bool, List[str]]:
    """Check database health and data availability."""
    issues = []
    
    try:
        from src.data.config import DB_PATH, SYMBOLS
        
        if not os.path.exists(DB_PATH):
            issues.append(f"Database file not found: {DB_PATH}")
            return False, issues
        
        # Check database connectivity and recent data
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'price_data' not in tables:
            issues.append("price_data table not found")
        else:
            # Check for recent data (last 24 hours)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "SELECT COUNT(*) FROM price_data WHERE timestamp > ?", 
                (yesterday,)
            )
            recent_count = cursor.fetchone()[0]
            
            if recent_count == 0:
                issues.append("No recent data (last 24 hours)")
            
            # Check data for each configured symbol
            missing_symbols = []
            for symbol in SYMBOLS[:3]:  # Check first 3 symbols
                cursor.execute(
                    "SELECT COUNT(*) FROM price_data WHERE symbol = ? AND timestamp > ?",
                    (symbol, yesterday)
                )
                if cursor.fetchone()[0] == 0:
                    missing_symbols.append(symbol)
            
            if missing_symbols:
                issues.append(f"Missing recent data for: {', '.join(missing_symbols)}")
        
        conn.close()
        
    except Exception as e:
        issues.append(f"Database check failed: {e}")
    
    return len(issues) == 0, issues

def check_file_structure() -> Tuple[bool, List[str]]:
    """Check that required files and directories exist."""
    issues = []
    
    required_dirs = ['apps', 'src/core', 'src/data', 'docs/api', 'tests']
    required_files = ['apps/trader.py', 'src/core/ai_brain.py', 'src/data/config.py']
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            issues.append(f"Missing directory: {directory}")
    
    for file in required_files:
        if not os.path.exists(file):
            issues.append(f"Missing file: {file}")
    
    return len(issues) == 0, issues

def check_apis() -> Tuple[bool, List[str]]:
    """Check API connectivity and authentication."""
    issues = []
    
    try:
        from src.data_collector import DataCollector
        from src.core.ai_brain import ClaudeAI
        
        # Test data collector initialization (includes API checks)
        collector = DataCollector()
        if len(collector.apis) == 0:
            issues.append("No data APIs available")
        
        # Test AI brain initialization (Claude API)
        ai = ClaudeAI()
        if not hasattr(ai, 'client') or ai.client is None:
            issues.append("Claude AI client not initialized")
        
    except Exception as e:
        issues.append(f"API check failed: {e}")
    
    return len(issues) == 0, issues

def run_system_tests() -> Tuple[bool, List[str]]:
    """Run basic system functionality tests."""
    issues = []
    
    try:
        # Test critical system functions
        from src.core.indicator_engine import calculate_all_indicators
        from src.core.risk_manager import SimpleRiskManager
        import pandas as pd
        import numpy as np
        
        # Create test data
        test_df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=50, freq='5min'),
            'open': np.random.uniform(95, 105, 50),
            'high': np.random.uniform(100, 110, 50), 
            'low': np.random.uniform(90, 100, 50),
            'close': np.random.uniform(95, 105, 50),
            'volume': np.random.uniform(900000, 1100000, 50)
        })
        
        # Test indicator calculation
        indicators = calculate_all_indicators(test_df)
        if not indicators or len(indicators) == 0:
            issues.append("Indicator calculation failed")
        
        # Test risk management
        risk_mgr = SimpleRiskManager()
        risk_params = risk_mgr.calculate_risk_parameters(
            symbol="TEST", 
            signal_type="BUY", 
            entry_price=100.0, 
            capital=10000
        )
        if risk_params.position_size <= 0:
            issues.append("Risk management calculation failed")
        
    except Exception as e:
        issues.append(f"System test failed: {e}")
    
    return len(issues) == 0, issues

def main():
    """Run comprehensive health check."""
    parser = argparse.ArgumentParser(description='System Health Check')
    parser.add_argument('--quick', action='store_true', help='Run quick check only')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output')
    args = parser.parse_args()
    
    print("=" * 60)
    print("SYSTEM HEALTH CHECK")
    print("=" * 60)
    
    if args.quick:
        checks = [
            ("File Structure", check_file_structure),
            ("Configuration", check_configuration),
            ("Imports", check_imports)
        ]
    else:
        checks = [
            ("File Structure", check_file_structure),
            ("Configuration", check_configuration), 
            ("Imports", check_imports),
            ("Database", check_database),
            ("APIs", check_apis),
            ("System Tests", run_system_tests)
        ]
    
    all_pass = True
    results = {}
    
    for name, check_func in checks:
        success, issues = check_func()
        results[name] = (success, issues)
        
        if success:
            print(f"✅ {name}: OK")
        else:
            print(f"❌ {name}: FAILED")
            if args.verbose or len(issues) <= 3:
                for issue in issues:
                    print(f"   - {issue}")
            elif len(issues) > 3:
                print(f"   - {issues[0]}")
                print(f"   - ... and {len(issues)-1} more issues")
            all_pass = False
    
    print("=" * 60)
    
    if all_pass:
        print("✅ ALL CHECKS PASS - System healthy!")
        return 0
    else:
        print("❌ HEALTH CHECK FAILED - Issues detected")
        if not args.verbose:
            print("   Run with --verbose for detailed error information")
        return 1

if __name__ == "__main__":
    sys.exit(main())