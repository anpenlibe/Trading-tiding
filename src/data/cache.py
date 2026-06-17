"""Memory cache implementation for market data."""

import time
from typing import Dict, Tuple, Any, Optional
from src.utils.logger import setup_logger
from src.data.config import CACHE_TTL_SECONDS

logger = setup_logger(__name__, 'cache.log')


class MemoryCache:
    """In-memory cache with TTL support."""
    
    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS):
        """Initialize cache with time-to-live."""
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.ttl = ttl_seconds
        logger.info(f"Memory cache initialized with TTL: {ttl_seconds}s")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                logger.debug(f"Cache hit: {key}")
                return value
            else:
                del self.cache[key]
                logger.debug(f"Cache expired: {key}")
        return None
    
    def set(self, key: str, value: Any):
        """Set value in cache."""
        self.cache[key] = (value, time.time())
        logger.debug(f"Cache set: {key}")
    
    def clear_expired(self):
        """Remove all expired entries."""
        current_time = time.time()
        expired = [k for k, (_, ts) in self.cache.items() 
                  if current_time - ts >= self.ttl]
        for key in expired:
            del self.cache[key]
        if expired:
            logger.debug(f"Cleared {len(expired)} expired entries")
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)
    
    def keys(self) -> list:
        """Get all cache keys."""
        return list(self.cache.keys())