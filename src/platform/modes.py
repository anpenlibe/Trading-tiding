"""Trading-mode safety system.

Enforces that live trading runs only on a verified live source. The mode
(PAPER/LIVE/BACKTEST) is authoritative: TradingSafetyConfig's __post_init__
derives the safety flags from it, overriding any passed in.
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass
from src.platform.types import MarketData
from src.platform.errors import TradingSystemError
from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'trading_modes.log')


class TradingMode(Enum):
    """Trading mode enumeration for safety"""
    PAPER = "paper"      # Paper trading - can use any data source
    LIVE = "live"        # Live trading - MUST use verified live data only
    BACKTEST = "backtest"  # Historical simulation - uses historical data


@dataclass
class TradingSafetyConfig:
    """Configuration for trading safety checks"""
    mode: TradingMode
    require_live_data: bool = False
    require_user_confirmation: bool = False

    def __post_init__(self):
        """Set safety defaults based on trading mode"""
        if self.mode == TradingMode.LIVE:
            self.require_live_data = True
            self.require_user_confirmation = True
        elif self.mode == TradingMode.PAPER:
            self.require_live_data = False
            self.require_user_confirmation = False
        elif self.mode == TradingMode.BACKTEST:
            self.require_live_data = False
            self.require_user_confirmation = False


class TradingSafetyValidator:
    """Validates data sources and trading mode safety"""
    
    def __init__(self, safety_config: TradingSafetyConfig):
        self.config = safety_config
        self.live_confirmation_given = False
        
    def validate_market_data(self, market_data: MarketData) -> bool:
        """
        Validate that market data is appropriate for current trading mode.
        
        Args:
            market_data: Market data to validate
            
        Returns:
            bool: True if data is safe to use
            
        Raises:
            TradingSystemError: If data source is unsafe for current mode
        """
        if not market_data:
            raise TradingSystemError("No market data provided for validation")
        
        data_source = market_data.source.lower()

        # CRITICAL: live trading must run on a verified live source. (Mock no
        # longer exists, but this still rejects any non-live source string.)
        if self.config.mode == TradingMode.LIVE:
            if data_source not in ["zerodha", "live"]:
                raise TradingSystemError(
                    f"🚨 SAFETY VIOLATION: Live trading requires a verified live data "
                    f"source. Got: {data_source}. Expected: 'zerodha' or 'live'"
                )
            if not self._is_live_data_fresh(market_data):
                logger.warning(f"Live data may be stale: {market_data.timestamp}")

        elif self.config.mode == TradingMode.PAPER:
            logger.debug(f"Using {data_source} data for paper trading")

        elif self.config.mode == TradingMode.BACKTEST:
            if not (data_source.startswith("historical") or data_source.startswith("simulation")):
                logger.warning(f"Backtest using non-historical data: {data_source}")

        return True
    
    def _is_live_data_fresh(self, market_data: MarketData) -> bool:
        """Check if live data is reasonably fresh (within last few minutes)"""
        from datetime import datetime, timedelta
        
        if not market_data.timestamp:
            return False
            
        now = datetime.now()
        data_time = market_data.timestamp
        
        # Convert to datetime if needed
        if hasattr(data_time, 'to_pydatetime'):
            data_time = data_time.to_pydatetime()
        
        # Data should be within last 10 minutes for live trading
        max_age = timedelta(minutes=10)
        age = now - data_time
        
        return age <= max_age
    
    def require_live_trading_confirmation(self) -> bool:
        """
        Require explicit user confirmation for live trading mode.
        
        Returns:
            bool: True if confirmation given, False otherwise
        """
        if self.config.mode != TradingMode.LIVE:
            return True  # No confirmation needed for non-live modes
        
        if self.live_confirmation_given:
            return True  # Already confirmed
        
        print("🚨" * 20)
        print("⚠️  LIVE TRADING MODE WARNING")
        print("🚨" * 20)
        print()
        print("You are about to start LIVE TRADING with REAL MONEY.")
        print("This system will execute actual trades on the stock market.")
        print()
        print("RISKS:")
        print("• Real financial losses possible")
        print("• Market volatility can cause rapid losses")  
        print("• System bugs could result in unexpected trades")
        print("• No guarantee of profits")
        print()
        print("SAFEGUARDS ENABLED:")
        print("• Only verified live (Zerodha) data accepted")
        print("• Live data source validation ENABLED")
        print("• Position size limits ACTIVE")
        print("• Stop loss protection ACTIVE")
        print()
        
        confirmation1 = input("Type 'I UNDERSTAND THE RISKS' to continue: ")
        if confirmation1 != "I UNDERSTAND THE RISKS":
            print("❌ Live trading confirmation failed.")
            return False
        
        confirmation2 = input("Type 'START LIVE TRADING' to confirm: ")
        if confirmation2 != "START LIVE TRADING":
            print("❌ Live trading confirmation failed.")
            return False
        
        print("✅ Live trading confirmed. Starting in 3 seconds...")
        import time
        for i in range(3, 0, -1):
            print(f"⏰ {i}...")
            time.sleep(1)
        
        self.live_confirmation_given = True
        logger.critical("LIVE TRADING MODE CONFIRMED BY USER")
        return True
    
    def validate_trading_session_start(self) -> bool:
        """
        Complete validation before starting a trading session.
        
        Returns:
            bool: True if safe to start trading
        """
        logger.info(f"Validating trading session start in {self.config.mode.value} mode")
        
        # Check if user confirmation is required and obtained
        if self.config.require_user_confirmation:
            if not self.require_live_trading_confirmation():
                raise TradingSystemError("Live trading confirmation required but not provided")
        
        logger.info("Trading session validation passed")
        return True


# Default configurations per mode. Only `mode` is given — __post_init__ derives
# the safety flags, so passing them here would be redundant (and overridden).
PAPER_TRADING_CONFIG = TradingSafetyConfig(mode=TradingMode.PAPER)
LIVE_TRADING_CONFIG = TradingSafetyConfig(mode=TradingMode.LIVE)
BACKTEST_CONFIG = TradingSafetyConfig(mode=TradingMode.BACKTEST)