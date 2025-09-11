#!/usr/bin/env python3
"""Comprehensive system health check."""

import sys
import os
from typing import Dict, List, Tuple

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
    """Check database health."""
    issues = []
    
    try:
        from src.utils.db_optimizer import DatabaseOptimizer
        optimizer = DatabaseOptimizer()
        metrics = optimizer.analyze_performance()
        
        if metrics['size_mb'] > 1000:
            issues.append(f"Database too large: {metrics['size_mb']:.1f} MB")
        
        optimizer.close()
    except Exception as e:
        issues.append(f"Database check failed: {e}")
    
    return len(issues) == 0, issues

def check_file_structure() -> Tuple[bool, List[str]]:
    """Check that required files and directories exist."""
    issues = []
    
    required_dirs = ['apps', 'src/core', 'src/data', 'docs/api', 'tests']
    required_files = ['apps/trader.py', 'src/core/ai_brain.py', 'src/config.py']
    
    for directory in required_dirs:
        if not os.path.exists(directory):
            issues.append(f"Missing directory: {directory}")
    
    for file in required_files:
        if not os.path.exists(file):
            issues.append(f"Missing file: {file}")
    
    return len(issues) == 0, issues

def main():
    """Run comprehensive health check."""
    print("=" * 60)
    print("SYSTEM HEALTH CHECK")
    print("=" * 60)
    
    checks = [
        ("File Structure", check_file_structure),
        ("Configuration", check_configuration),
        ("Imports", check_imports),
        ("Database", check_database)
    ]
    
    all_pass = True
    
    for name, check_func in checks:
        success, issues = check_func()
        
        if success:
            print(f"✅ {name}: OK")
        else:
            print(f"❌ {name}: FAILED")
            for issue in issues:
                print(f"   - {issue}")
            all_pass = False
    
    print("=" * 60)
    
    if all_pass:
        print("✅ ALL CHECKS PASS - System healthy!")
        return 0
    else:
        print("❌ HEALTH CHECK FAILED - Issues detected")
        return 1

if __name__ == "__main__":
    sys.exit(main())