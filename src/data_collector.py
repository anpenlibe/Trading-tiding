"""Enhanced data collector with robust error handling."""

import pandas as pd
from typing import List, Optional, Dict, Any
from collections import defaultdict

from src.data.cache import MemoryCache
from src.data.validator import DataValidator
from src.data.database import DatabaseManager
from src.data.data_sources import ZerodhaAPI, YahooFinanceAPI, MockAPI
from src.core.indicator_engine import calculate_all_indicators
from src.interfaces import BaseMarketDataAPI, MarketData
from src.data.config import SYMBOLS, CACHE_TTL_SECONDS, DB_PATH, MIN_DATA_FOR_INDICATORS
from src.utils.logger import setup_logger
from src.utils.retry import retry_with_backoff, CircuitBreaker
from src.exceptions import DataCollectionError, ValidationError, DatabaseError, TradingSystemError
from src.monitoring.performance import performance_tracker
from src.core.trading_modes import TradingSafetyValidator, PAPER_TRADING_CONFIG

logger = setup_logger(__name__, 'data_collector.log')


class DataCollector:
    """Data collector with enhanced error handling."""
    
    def __init__(self, safety_config=None):
        """Initialize with error handling."""
        logger.info("Initializing DataCollector with error handling")
        
        try:
            # Initialize components with error handling
            self.db = self._init_database()
            self.cache = MemoryCache(ttl_seconds=CACHE_TTL_SECONDS)
            self.validator = DataValidator()
            
            # Trading safety system integration
            self.safety_config = safety_config or PAPER_TRADING_CONFIG
            self.safety_validator = TradingSafetyValidator(self.safety_config)
            logger.info(f"DataCollector initialized in {self.safety_config.mode.value} mode")
            
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
        """Initialize data sources in priority order: Zerodha → Yahoo → (mock)."""
        apis: List[BaseMarketDataAPI] = []
        live_apis = []  # real/live sources only (mock excluded)

        def _register(api):
            apis.append(api)
            live_apis.append(api)
            self.api_circuit_breakers[api.__class__.__name__] = CircuitBreaker(
                failure_threshold=3, recovery_timeout=300  # 5 minutes
            )
            logger.info(f"Initialized {api.__class__.__name__}")

        # Priority 1: Zerodha (authenticated live data).
        try:
            zerodha = ZerodhaAPI()
            if zerodha.is_available():
                _register(zerodha)
        except Exception as e:
            logger.warning(f"Failed to initialize ZerodhaAPI: {e}")

        # Priority 2: Yahoo Finance (real backup). Include whenever yfinance is
        # importable; per-fetch availability/rate-limiting is handled internally,
        # so we avoid a network probe on every startup.
        try:
            yahoo = YahooFinanceAPI()
            if getattr(yahoo, "yf", None) is not None:
                _register(yahoo)
        except Exception as e:
            logger.warning(f"Failed to initialize YahooFinanceAPI: {e}")

        # Live trading requires a real source; mock is NEVER allowed.
        if self.safety_config.mode.value == 'live':
            if not live_apis:
                error_msg = (
                    "🚨 No live data source available for LIVE trading. Configure Zerodha "
                    "(or ensure Yahoo Finance is reachable), or switch to paper trading."
                )
                logger.critical(error_msg)
                raise TradingSystemError(error_msg)
            return apis

        # Paper / backtest: add Mock as a guaranteed last-resort fallback so a real
        # source that authenticates but then fails to fetch can't dead-end a cycle.
        if self.safety_config.allow_mock_fallback:
            apis.append(MockAPI())
            self.api_circuit_breakers['MockAPI'] = CircuitBreaker()
            if not live_apis:
                logger.warning(
                    f"No live APIs available; using mock data in {self.safety_config.mode.value} mode"
                )
        elif not apis:
            error_msg = (
                f"🚨 No live data source in {self.safety_config.mode.value} mode and mock "
                "fallback is disabled. Configure a live data source before trading."
            )
            logger.critical(error_msg)
            raise TradingSystemError(error_msg)

        return apis
    
    @staticmethod
    def _fetch_or_raise(api: BaseMarketDataAPI, symbol: str) -> MarketData:
        """Fetch OHLC, raising on an empty result so the circuit breaker counts
        it as a failure. Uses a plain RuntimeError (not TradingSystemError) so the
        collect loop's generic handler catches it and moves to the next source."""
        data = api.fetch_ohlc(symbol)
        if not data:
            raise RuntimeError(f"{api.__class__.__name__} returned no data for {symbol}")
        return data

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

                    # Use circuit breaker if available. Route through a wrapper
                    # that raises on an empty result so a persistently-failing
                    # source (e.g. expired-token Zerodha, rate-limited Yahoo —
                    # both return None rather than raising) actually trips its
                    # breaker after a few misses and is then skipped fast, instead
                    # of being re-probed (~seconds each) for every symbol.
                    if circuit_breaker:
                        market_data = circuit_breaker.call(self._fetch_or_raise, api, symbol)
                    else:
                        market_data = api.fetch_ohlc(symbol)
                        if not market_data:
                            last_error = f"{api_name} returned no data"
                            continue
                    
                    # Validate data
                    is_valid, error = self.validator.validate(market_data)
                    if not is_valid:
                        raise ValidationError(f"Validation failed: {error}")
                    
                    # CRITICAL: Validate data source against trading mode
                    self.safety_validator.validate_market_data(market_data)
                    
                    # Store in database
                    self._store_data(symbol, market_data)
                    
                    # Cache the data
                    self.cache.set(f"{symbol}_recent", market_data)
                    
                    self.stats['successful_fetches'] += 1
                    logger.info(f"Successfully collected data for {symbol} from {api_name}")
                    return True
                    
                except TradingSystemError:
                    # CRITICAL: Re-raise safety violations immediately - do not catch
                    raise
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
    
    def get_recent_data(self, symbol: str, periods: int = 50) -> Optional[pd.DataFrame]:
        """Get recent data with error handling."""
        try:
            return self.db.get_recent_data(symbol, periods)
        except Exception as e:
            logger.error(f"Failed to get recent data for {symbol}: {e}")
            return None
    
    def process_and_save(self, data: MarketData) -> bool:
        """Process and save market data with indicators."""
        try:
            # CRITICAL: Validate data source against trading mode
            self.safety_validator.validate_market_data(data)
            
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
            
        except TradingSystemError:
            # CRITICAL: Re-raise safety violations immediately - do not catch
            raise
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
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate collection summary with validation statistics."""
        try:
            stats = self.get_stats()
            return {
                'collection_stats': {
                    'successful_fetches': stats.get('successful_fetches', 0),
                    'failed_fetches': stats.get('failed_fetches', 0),
                    'cache_hits': stats.get('cache_hits', 0),
                    'validation_failures': stats.get('validation_failures', 0)
                },
                'validation_stats': stats.get('validation_stats', {}),
                'database_stats': stats.get('database_stats', {}),
                'api_calls': dict(stats.get('api_calls', {}))
            }
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            return {'error': str(e)}
    
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


# Factory functions for safe DataCollector creation
def create_paper_trading_collector() -> DataCollector:
    """Create DataCollector for paper trading (allows mock data)."""
    from src.core.trading_modes import PAPER_TRADING_CONFIG
    return DataCollector(safety_config=PAPER_TRADING_CONFIG)


def create_live_trading_collector() -> DataCollector:
    """Create DataCollector for live trading (strict safety checks)."""
    from src.core.trading_modes import LIVE_TRADING_CONFIG
    collector = DataCollector(safety_config=LIVE_TRADING_CONFIG)
    
    # Require explicit user confirmation for live trading
    collector.safety_validator.validate_trading_session_start()
    
    return collector


def create_backtest_collector() -> DataCollector:
    """Create DataCollector for backtesting (historical data only)."""
    from src.core.trading_modes import BACKTEST_CONFIG
    return DataCollector(safety_config=BACKTEST_CONFIG)