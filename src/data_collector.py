"""Enhanced data collector with robust error handling."""

import time
import pandas as pd
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict

from src.data.cache import MemoryCache
from src.data.validator import DataValidator
from src.data.database import DatabaseManager
from src.data_sources import ZerodhaAPI, MockAPI
from src.indicator_engine import calculate_all_indicators
from src.interfaces import BaseMarketDataAPI, MarketData
from src.config import SYMBOLS, CACHE_TTL_SECONDS, DB_PATH, MIN_DATA_FOR_INDICATORS
from src.utils.logger import setup_logger
from src.utils.retry import retry_with_backoff, CircuitBreaker
from src.exceptions import DataCollectionError, ValidationError, DatabaseError
from src.monitoring.performance import performance_tracker

logger = setup_logger(__name__, 'data_collector.log')


class DataCollector:
    """Data collector with enhanced error handling."""
    
    def __init__(self):
        """Initialize with error handling."""
        logger.info("Initializing DataCollector with error handling")
        
        try:
            # Initialize components with error handling
            self.db = self._init_database()
            self.cache = MemoryCache(ttl_seconds=CACHE_TTL_SECONDS)
            self.validator = DataValidator()
            
            # Circuit breaker for each API
            self.api_circuit_breakers = {}
            
            # Initialize APIs with error handling
            self.apis = self._init_apis()
            
            # Statistics
            self.stats = {
                'api_calls': defaultdict(int),
                'successful_fetches': 0,
                'failed_fetches': 0,
                'cache_hits': 0,
                'validation_failures': 0
            }
            
            logger.info(f"DataCollector initialized with {len(self.apis)} APIs")
        except Exception as e:
            logger.error(f"Failed to initialize DataCollector: {e}")
            raise DataCollectionError(f"Initialization failed: {e}")
    
    @retry_with_backoff(max_retries=3, exceptions=(DatabaseError,))
    def _init_database(self) -> DatabaseManager:
        """Initialize database with retry logic."""
        try:
            return DatabaseManager(DB_PATH)
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {e}")
    
    def _init_apis(self) -> List[BaseMarketDataAPI]:
        """Initialize APIs with circuit breakers."""
        apis = []
        
        for api_class in [ZerodhaAPI, MockAPI]:
            try:
                api = api_class()
                if api.is_available():
                    apis.append(api)
                    # Create circuit breaker for this API
                    self.api_circuit_breakers[api.__class__.__name__] = CircuitBreaker(
                        failure_threshold=3,
                        recovery_timeout=300  # 5 minutes
                    )
                    logger.info(f"Initialized {api.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Failed to initialize {api_class.__name__}: {e}")
        
        if not apis:
            logger.warning("No APIs available, using fallback mock data")
            # Force MockAPI as fallback
            mock = MockAPI()
            apis.append(mock)
            self.api_circuit_breakers['MockAPI'] = CircuitBreaker()
        
        return apis
    
    @retry_with_backoff(max_retries=2, exceptions=(DataCollectionError,))
    @performance_tracker("data_collection")
    def collect_and_store(self, symbol: str) -> bool:
        """Collect data with comprehensive error handling."""
        try:
            # Check cache first
            cached_data = self.cache.get(f"{symbol}_recent")
            if cached_data:
                logger.debug(f"Using cached data for {symbol}")
                self.stats['cache_hits'] += 1
                return True
            
            # Try each API with circuit breaker
            last_error = None
            for api in self.apis:
                api_name = api.__class__.__name__
                circuit_breaker = self.api_circuit_breakers.get(api_name)
                
                try:
                    self.stats['api_calls'][api.get_name()] += 1
                    
                    # Use circuit breaker if available
                    if circuit_breaker:
                        market_data = circuit_breaker.call(api.fetch_ohlc, symbol)
                    else:
                        market_data = api.fetch_ohlc(symbol)
                    
                    if not market_data:
                        continue
                    
                    # Validate data
                    is_valid, error = self.validator.validate(market_data)
                    if not is_valid:
                        raise ValidationError(f"Validation failed: {error}")
                    
                    # Store in database
                    self._store_data(symbol, market_data)
                    
                    # Cache the data
                    self.cache.set(f"{symbol}_recent", market_data)
                    
                    self.stats['successful_fetches'] += 1
                    logger.info(f"Successfully collected data for {symbol} from {api_name}")
                    return True
                    
                except ValidationError as e:
                    logger.warning(f"Validation error for {symbol} from {api_name}: {e}")
                    self.stats['validation_failures'] += 1
                    last_error = e
                    continue
                except Exception as e:
                    logger.error(f"Failed to collect from {api_name}: {e}")
                    last_error = e
                    continue
            
            # All APIs failed
            raise DataCollectionError(f"All APIs failed for {symbol}. Last error: {last_error}")
            
        except Exception as e:
            logger.error(f"Critical error collecting data for {symbol}: {e}")
            self.stats['failed_fetches'] += 1
            return False
    
    @retry_with_backoff(max_retries=2, exceptions=(DatabaseError,))
    def _store_data(self, symbol: str, market_data: MarketData):
        """Store data with retry logic."""
        try:
            if not self.db.save_market_data(market_data):
                raise DatabaseError("Failed to save market data")
                
            # Calculate and store indicators
            df = self.db.get_recent_data(symbol)
            if len(df) >= MIN_DATA_FOR_INDICATORS:
                try:
                    indicators = calculate_all_indicators(df)
                    self.db.save_indicators(symbol, market_data.timestamp, indicators)
                    logger.debug(f"Calculated indicators for {symbol}")
                except Exception as e:
                    logger.warning(f"Failed to calculate indicators: {e}")
                    # Don't fail the entire operation if indicators fail
                    
        except Exception as e:
            raise DatabaseError(f"Database storage failed: {e}")
    
    def collect_all_symbols(self) -> Dict[str, bool]:
        """Collect data for all configured symbols."""
        logger.info(f"Starting collection for {len(SYMBOLS)} symbols")
        start_time = time.time()
        
        results = {}
        for symbol in SYMBOLS:
            try:
                success = self.collect_and_store(symbol)
                results[symbol] = success
                
                # Small delay to avoid overwhelming APIs
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Unexpected error collecting {symbol}: {e}")
                results[symbol] = False
        
        duration = time.time() - start_time
        successful = sum(1 for success in results.values() if success)
        
        logger.info(f"Collection complete: {successful}/{len(SYMBOLS)} symbols in {duration:.1f}s")
        return results
    
    def get_recent_data(self, symbol: str, periods: int = 50) -> Optional[pd.DataFrame]:
        """Get recent data with error handling."""
        try:
            return self.db.get_recent_data(symbol, periods)
        except Exception as e:
            logger.error(f"Failed to get recent data for {symbol}: {e}")
            return None
    
    def fetch_with_fallback(self, symbol: str) -> Optional[MarketData]:
        """Fetch data with automatic fallback to backup sources."""
        # Check cache first
        cache_key = f"ohlc_{symbol}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            self.stats['cache_hits'] += 1
            return cached_data
        
        # Try each API in order
        for api in self.apis:
            try:
                self.stats['api_calls'][api.get_name()] += 1
                data = api.fetch_ohlc(symbol)
                
                if data:
                    # Validate data
                    is_valid, error = self.validator.validate(data)
                    if is_valid:
                        # Cache successful fetch
                        self.cache.set(cache_key, data)
                        return data
                    else:
                        logger.warning(f"Validation failed for {symbol} from {api.get_name()}: {error}")
                        
            except Exception as e:
                logger.warning(f"API {api.get_name()} failed for {symbol}: {e}")
                continue
        
        return None
    
    def process_and_save(self, data: MarketData) -> bool:
        """Process and save market data with indicators."""
        try:
            # Save market data
            if not self.db.save_market_data(data):
                return False
            
            # Get recent data for indicators
            df = self.db.get_recent_data(data.symbol)
            if len(df) >= MIN_DATA_FOR_INDICATORS:
                # Calculate indicators
                indicators = calculate_all_indicators(df)
                
                # Save indicators
                self.db.save_indicators(data.symbol, data.timestamp, indicators)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process and save data for {data.symbol}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        return {
            **self.stats,
            'cache_size': self.cache.size(),
            'validation_stats': self.validator.get_stats(),
            'database_stats': self.db.get_stats()
        }
    
    def close(self):
        """Clean shutdown with error handling."""
        try:
            if hasattr(self, 'db'):
                self.db.close()
            if hasattr(self, 'cache'):
                self.cache.clear()
            logger.info("DataCollector shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    # Legacy compatibility methods
    def save_market_data(self, data: MarketData) -> bool:
        """Legacy method for compatibility."""
        return self.db.save_market_data(data)
    
    def save_indicators(self, symbol: str, timestamp: datetime, indicators: Dict[str, float]) -> bool:
        """Legacy method for compatibility."""
        return self.db.save_indicators(symbol, timestamp, indicators)