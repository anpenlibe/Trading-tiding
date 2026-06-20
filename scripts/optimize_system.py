#!/usr/bin/env python3
"""Complete system optimization script (DB optimize + performance dashboard)."""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.marketdata.maintenance import run_optimization
from src.monitoring.dashboard import display_performance_dashboard

def main():
    print("🚀 SYSTEM OPTIMIZATION STARTING")
    print("="*60)
    
    # Run database optimization
    run_optimization()
    
    # Display performance
    display_performance_dashboard()
    
    print("\n✅ OPTIMIZATION COMPLETE!")

if __name__ == "__main__":
    main()