"""Market data validation utilities."""

from typing import Tuple, Optional, Dict
from collections import defaultdict

from src.interfaces import MarketData
from src.data.config import VALIDATION_MAX_PRICE_CHANGE, VALIDATION_MIN_VOLUME


class DataValidator:
    """Validate OHLCV bars for quality, tracking reject reasons per outcome."""

    def __init__(self):
        self.max_price_change = VALIDATION_MAX_PRICE_CHANGE
        self.min_volume = VALIDATION_MIN_VOLUME
        self.validation_stats = defaultdict(int)

    def validate(self, data: MarketData,
                 previous_close: Optional[float] = None) -> Tuple[bool, Optional[str]]:
        """Validate one OHLCV bar. Returns ``(is_valid, error_message)``."""
        # Reject zero/negative prices.
        if any(getattr(data, field) <= 0 for field in ('open', 'high', 'low', 'close')):
            self.validation_stats['zero_price'] += 1
            return False, "Invalid price: zero or negative"

        if data.high < data.low:
            self.validation_stats['high_low_mismatch'] += 1
            return False, "High price less than low price"

        # OHLC consistency with tolerance (live bars may mix timeframes): high
        # should top open/close and low should sit under them, within 0.5% or Rs1.
        max_oc = max(data.open, data.close)
        min_oc = min(data.open, data.close)
        price_tolerance = max(max_oc * 0.005, 1.0)

        if data.high < (max_oc - price_tolerance):
            self.validation_stats['ohlc_mismatch'] += 1
            return False, f"High ({data.high}) significantly low vs Open/Close ({max_oc})"

        if data.low > (min_oc + price_tolerance):
            self.validation_stats['ohlc_mismatch'] += 1
            return False, f"Low ({data.low}) significantly high vs Open/Close ({min_oc})"

        # Low volume signals market-closed or bad data.
        # TODO: relax with a market-hours check when switching to live trading.
        if data.volume < self.min_volume:
            self.validation_stats['low_volume'] += 1
            return False, f"Volume too low: {data.volume}"

        if previous_close:
            price_change = abs(data.close - previous_close) / previous_close
            if price_change > self.max_price_change:
                self.validation_stats['circuit_breaker'] += 1
                return False, f"Price change {price_change:.2%} exceeds limit"

        self.validation_stats['valid'] += 1
        return True, None

    def get_stats(self) -> Dict[str, int]:
        """Counts of validation outcomes by reason (including 'valid')."""
        return dict(self.validation_stats)
