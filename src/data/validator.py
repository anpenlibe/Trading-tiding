"""Market data validation utilities."""

from typing import Tuple, Optional, Dict
from collections import defaultdict
from src.interfaces import MarketData
from src.data.config import VALIDATION_MAX_PRICE_CHANGE, VALIDATION_MIN_VOLUME
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'validator.log')


class DataValidator:
    """Validate market data for quality and consistency."""
    
    def __init__(self):
        """Initialize validator with thresholds."""
        self.max_price_change = VALIDATION_MAX_PRICE_CHANGE
        self.min_volume = VALIDATION_MIN_VOLUME
        self.validation_stats = defaultdict(int)
    
    def validate(self, data: MarketData, 
                previous_close: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate market data.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for zero or negative prices
        if any(getattr(data, field) <= 0 for field in ['open', 'high', 'low', 'close']):
            self.validation_stats['zero_price'] += 1
            return False, "Invalid price: zero or negative"
        
        # Check high/low logic
        if data.high < data.low:
            self.validation_stats['high_low_mismatch'] += 1
            return False, "High price less than low price"
        
        # Check OHLC relationships with tolerance for live data
        max_oc = max(data.open, data.close)
        min_oc = min(data.open, data.close)
        
        # Allow tolerance for live data inconsistencies (0.5% or minimum ₹1)
        price_tolerance = max(max_oc * 0.005, 1.0)  # 0.5% or ₹1, whichever is higher
        
        # For live data, be more lenient as OHLC might be from different timeframes
        # High should be >= max of open/close (with tolerance)
        if data.high < (max_oc - price_tolerance):
            self.validation_stats['ohlc_mismatch'] += 1
            return False, f"High ({data.high}) significantly low vs Open/Close ({max_oc})"
        
        # Low should be <= min of open/close (with tolerance) 
        if data.low > (min_oc + price_tolerance):
            self.validation_stats['ohlc_mismatch'] += 1
            return False, f"Low ({data.low}) significantly high vs Open/Close ({min_oc})"
        
        # Check volume
        if data.volume < self.min_volume:
            # TODO: Add market hours check here when switching to live trading
            # For now, volume < 100 indicates either market closed or data quality issues
            # During live trading hours, this is appropriate validation
            # During testing/backtesting, this may need to be relaxed
            self.validation_stats['low_volume'] += 1
            return False, f"Volume too low: {data.volume}"
        
        # Check price change if previous close available
        if previous_close:
            price_change = abs(data.close - previous_close) / previous_close
            if price_change > self.max_price_change:
                self.validation_stats['circuit_breaker'] += 1
                return False, f"Price change {price_change:.2%} exceeds limit"
        
        self.validation_stats['valid'] += 1
        return True, None
    
    def get_stats(self) -> Dict[str, int]:
        """Get validation statistics."""
        return dict(self.validation_stats)
    
    def reset_stats(self):
        """Reset validation statistics."""
        self.validation_stats.clear()
        logger.info("Validation stats reset")
    
    def is_data_quality_good(self, threshold: float = 0.8) -> bool:
        """Check if overall data quality is above threshold."""
        total = sum(self.validation_stats.values())
        if total == 0:
            return True
        valid_ratio = self.validation_stats['valid'] / total
        return valid_ratio >= threshold