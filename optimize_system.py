#!/usr/bin/env python3
"""Complete system optimization script."""

from src.utils.db_optimizer import run_optimization
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