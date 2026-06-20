"""In-memory TTL cache for market data."""

import time
from typing import Dict, Tuple, Any, Optional

from src.platform.logger import setup_logger
from src.platform.config import CACHE_TTL_SECONDS

logger = setup_logger(__name__, 'cache.log')


class MemoryCache:
    """In-memory cache with per-entry time-to-live (lazy eviction on get)."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.ttl = ttl_seconds
        logger.info(f"Memory cache initialized with TTL: {ttl_seconds}s")

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value if present and unexpired, else None."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit: {key}")
                return value
            del self.cache[key]
            logger.debug(f"Cache expired: {key}")
        return None

    def set(self, key: str, value: Any):
        """Store value under key, stamped with the current time."""
        self.cache[key] = (value, time.time())
        logger.debug(f"Cache set: {key}")

    def clear(self):
        """Drop all entries."""
        self.cache.clear()
        logger.info("Cache cleared")

    def size(self) -> int:
        """Number of entries currently held (incl. not-yet-evicted expired)."""
        return len(self.cache)
