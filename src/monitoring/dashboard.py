"""Performance monitoring dashboard."""

from src.monitoring.performance import get_monitor
from src.utils.db_optimizer import DatabaseOptimizer


def display_performance_dashboard():
    """Display comprehensive performance metrics."""
    print("\n" + "="*60)
    print("SYSTEM PERFORMANCE DASHBOARD")
    print("="*60)
    
    monitor = get_monitor()
    stats = monitor.get_statistics()
    
    # System metrics
    print("\n📊 System Resources:")
    sys_stats = stats['system']
    print(f"  CPU Usage: {sys_stats['cpu_percent']:.1f}%")
    print(f"  Memory Usage: {sys_stats['memory_percent']:.1f}%")
    print(f"  Disk Usage: {sys_stats['disk_usage_percent']:.1f}%")
    print(f"  Uptime: {stats['uptime_seconds']/3600:.1f} hours")
    
    # Operation metrics
    print("\n⚡ Operation Performance:")
    for category, metrics in stats['operations'].items():
        print(f"\n  {category}:")
        print(f"    Count: {metrics['count']}")
        print(f"    Avg Time: {metrics['avg_duration']:.3f}s")
        print(f"    Success Rate: {metrics['success_rate']:.1%}")
    
    # Database metrics
    print("\n💾 Database Performance:")
    try:
        optimizer = DatabaseOptimizer()
        db_metrics = optimizer.analyze_performance()
        print(f"  Size: {db_metrics['size_mb']:.2f} MB")
        print(f"  Total Records: {sum(db_metrics['tables'].values()):,}")
        optimizer.close()
    except:
        print("  Unable to fetch database metrics")


if __name__ == "__main__":
    display_performance_dashboard()