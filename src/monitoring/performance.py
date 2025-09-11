"""System performance monitoring."""

import time
import psutil
import functools
from datetime import datetime
from typing import Dict, Any, Callable
from collections import deque
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'performance.log')


class PerformanceMonitor:
    """Monitor system performance metrics."""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.metrics = {
            'api_calls': deque(maxlen=window_size),
            'db_queries': deque(maxlen=window_size),
            'ai_decisions': deque(maxlen=window_size),
            'trades': deque(maxlen=window_size)
        }
        self.start_time = time.time()
    
    def record_metric(self, category: str, duration: float, success: bool = True):
        """Record a performance metric."""
        if category not in self.metrics:
            self.metrics[category] = deque(maxlen=self.window_size)
        
        self.metrics[category].append({
            'timestamp': time.time(),
            'duration': duration,
            'success': success
        })
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {
            'uptime_seconds': time.time() - self.start_time,
            'system': self._get_system_stats(),
            'operations': {}
        }
        
        for category, measurements in self.metrics.items():
            if measurements:
                durations = [m['duration'] for m in measurements]
                success_rate = sum(1 for m in measurements if m['success']) / len(measurements)
                
                stats['operations'][category] = {
                    'count': len(measurements),
                    'avg_duration': sum(durations) / len(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'success_rate': success_rate
                }
        
        return stats
    
    def _get_system_stats(self) -> Dict[str, Any]:
        """Get system resource usage."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage_percent': psutil.disk_usage('/').percent
        }


def performance_tracker(category: str):
    """Decorator to track function performance."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start
                # Log performance
                logger.debug(f"{category}.{func.__name__}: {duration:.3f}s")
                
        return wrapper
    return decorator


# Global monitor instance
_monitor = PerformanceMonitor()

def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    return _monitor