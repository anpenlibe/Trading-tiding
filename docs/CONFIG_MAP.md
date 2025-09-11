# Configuration Map
## Current Hardcoded Values Found

### data_collector.py
- Line 47: ttl_seconds=300 → Move to config.CACHE_TTL_SECONDS
- Line 87: max_price_change=0.20 → Move to config.VALIDATION_MAX_PRICE_CHANGE  
- Line 88: min_volume=100 → Move to config.VALIDATION_MIN_VOLUME
- Line 345: ttl_seconds=300 → Move to config.CACHE_TTL_SECONDS (duplicate)
- Line 290: periods=200 → Move to config.DEFAULT_PERIODS
- Line 453: len(df) >= 20 → Move to config.MIN_DATA_FOR_INDICATORS

### indicator_engine.py
- Line 48: period=14 → Move to config.RSI_PERIOD
- Line 96-97: MACD (12, 26, 9) → Move to config.MACD_FAST, MACD_SLOW, MACD_SIGNAL
- Line 62: calculate_sma(volume, 20) → Move to config.VOLUME_SMA_PERIOD

### ai_brain.py
- Line 130: tail(20) → Move to config.RECENT_DATA_LOOKBACK
- Line 130: lookback_period=20 (config.py) → Already in config but hardcoded elsewhere
- Line 347: len(self.decision_history) > 100 → Move to config.MAX_DECISION_HISTORY
- Line 434: periods=50 → Move to config.SIMULATION_PERIODS
- Line 437: base_price=2850 → Move to config.SIMULATION_BASE_PRICE

### data_sources.py
- Line 144: randint(100000, 1000000) → Move to config.MOCK_VOLUME_RANGE_MIN/MAX

### paper_trader.py
- Line 460: limit=50 → Move to config.DEFAULT_TRADE_HISTORY_LIMIT

### stock_registry.py
- Line 319: avg_daily_volume >= 2000000 → Move to config.MIN_LIQUIDITY_VOLUME

## SMA Periods Found
- Multiple references to SMA 20, 50, 200 periods throughout the codebase
- These should be consolidated into config.SMA_PERIODS = [20, 50, 200]

## Additional Hardcoded Values for Environment Configuration
- config.py Line 123: CLAUDE_MAX_TOKENS=1000 → Already configurable via env
- config.py Line 43: INITIAL_CAPITAL=10000.0 → Already configurable via env
- config.py Line 50: MAX_POSITION_SIZE=0.20 → Could be made configurable
- config.py Line 49: MIN_TRADE_VALUE=500.0 → Could be made configurable

## Files to be Modified
1. src/config.py - Add new configuration values
2. src/data_collector.py - Import and use config values
3. src/indicator_engine.py - Import and use config values  
4. src/ai_brain.py - Import and use config values
5. src/data_sources.py - Import and use config values
6. src/paper_trader.py - Import and use config values
7. src/stock_registry.py - Import and use config values
8. .env.template - Add new environment variables