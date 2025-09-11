"""Error tracking and monitoring."""

from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Any
import json

from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'error_tracker.log')


class ErrorTracker:
    """Track and analyze system errors."""
    
    def __init__(self, window_minutes: int = 60):
        """Initialize error tracker."""
        self.window_minutes = window_minutes
        self.errors = defaultdict(lambda: deque(maxlen=1000))
        self.error_counts = defaultdict(int)
        self.start_time = datetime.now()
    
    def record_error(self, module: str, error_type: str, details: str):
        """Record an error occurrence."""
        timestamp = datetime.now()
        error_record = {
            'timestamp': timestamp.isoformat(),
            'module': module,
            'type': error_type,
            'details': details
        }
        
        self.errors[module].append(error_record)
        self.error_counts[f"{module}:{error_type}"] += 1
        
        # Log if error rate is high
        recent_errors = self._get_recent_errors(module)
        if len(recent_errors) > 10:
            logger.warning(f"High error rate in {module}: {len(recent_errors)} errors in {self.window_minutes} minutes")
    
    def _get_recent_errors(self, module: str) -> List[Dict[str, Any]]:
        """Get errors within the time window."""
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        return [
            e for e in self.errors[module]
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive error summary."""
        summary = {
            'uptime': str(datetime.now() - self.start_time),
            'total_errors': sum(self.error_counts.values()),
            'modules_affected': len(self.errors),
            'top_errors': self._get_top_errors(5),
            'recent_errors': self._get_all_recent_errors(10),
            'error_rate': self._calculate_error_rate()
        }
        return summary
    
    def _get_top_errors(self, n: int) -> List[Dict[str, Any]]:
        """Get top N most frequent errors."""
        sorted_errors = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {'error': k, 'count': v}
            for k, v in sorted_errors[:n]
        ]
    
    def _get_all_recent_errors(self, n: int) -> List[Dict[str, Any]]:
        """Get N most recent errors across all modules."""
        all_errors = []
        for module_errors in self.errors.values():
            all_errors.extend(module_errors)
        
        # Sort by timestamp
        all_errors.sort(
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        return all_errors[:n]
    
    def _calculate_error_rate(self) -> float:
        """Calculate errors per minute."""
        uptime_minutes = (datetime.now() - self.start_time).total_seconds() / 60
        if uptime_minutes == 0:
            return 0.0
        
        total_errors = sum(self.error_counts.values())
        return total_errors / uptime_minutes
    
    def save_report(self, filepath: str):
        """Save error report to file."""
        summary = self.get_error_summary()
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Error report saved to {filepath}")