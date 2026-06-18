"""Centralized registry of tradable NSE stocks with sector/liquidity metadata.

Provides sector-based organization, market-cap and liquidity tags, and the
symbol-selection helpers behind the config.SYMBOLS strategy presets.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# Liquidity threshold - moved here to avoid circular import
MIN_LIQUIDITY_VOLUME = 1000000  # Minimum daily volume for liquidity filtering


class Sector(Enum):
    """Stock sectors for Indian market"""
    TECHNOLOGY = "technology"
    BANKING = "banking"
    ENERGY = "energy"
    FMCG = "fmcg"
    TELECOM = "telecom"
    PHARMA = "pharma"
    METALS = "metals"
    AUTO = "auto"
    INFRASTRUCTURE = "infrastructure"
    CHEMICALS = "chemicals"


class MarketCap(Enum):
    """Market capitalization categories"""
    LARGE_CAP = "large_cap"    # >₹20,000 crore
    MID_CAP = "mid_cap"        # ₹5,000-20,000 crore
    SMALL_CAP = "small_cap"    # <₹5,000 crore


class LiquidityRating(Enum):
    """Stock liquidity ratings"""
    HIGH = "high"       # Very liquid, tight spreads
    MEDIUM = "medium"   # Moderately liquid
    LOW = "low"         # Lower liquidity, wider spreads


@dataclass
class StockInfo:
    """Complete stock information"""
    symbol: str
    company_name: str
    sector: Sector
    market_cap: MarketCap
    liquidity: LiquidityRating
    is_index_stock: bool = False
    is_active: bool = True
    avg_daily_volume: Optional[int] = None
    typical_spread_bps: Optional[int] = None  # Basis points
    notes: Optional[str] = None


class StockRegistry:
    """
    Centralized stock registry with intelligent selection capabilities.

    Features:
    - Sector-based organization
    - Risk-based filtering
    - Liquidity-based selection
    - Priority lists for different strategies
    """

    def __init__(self):
        """Initialize the stock registry with Indian market stocks"""
        self.stocks: Dict[str, StockInfo] = {}
        self._initialize_stocks()

    def _initialize_stocks(self):
        """Initialize with curated list of Indian stocks"""

        # Technology Sector
        self._add_stock("TCS", "Tata Consultancy Services", Sector.TECHNOLOGY,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=5000000, typical_spread_bps=2,
                       notes="IT services leader, defensive stock")

        self._add_stock("INFY", "Infosys Limited", Sector.TECHNOLOGY,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=8000000, typical_spread_bps=2,
                       notes="IT services, global presence")

        self._add_stock("HCLTECH", "HCL Technologies", Sector.TECHNOLOGY,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=3000000, typical_spread_bps=3)

        self._add_stock("WIPRO", "Wipro Limited", Sector.TECHNOLOGY,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=4000000, typical_spread_bps=4)

        self._add_stock("TECHM", "Tech Mahindra", Sector.TECHNOLOGY,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=2500000, typical_spread_bps=5)

        # Banking Sector
        self._add_stock("HDFCBANK", "HDFC Bank", Sector.BANKING,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=6000000, typical_spread_bps=1,
                       notes="Private sector banking leader")

        self._add_stock("ICICIBANK", "ICICI Bank", Sector.BANKING,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=8000000, typical_spread_bps=2,
                       notes="Major private bank")

        self._add_stock("SBIN", "State Bank of India", Sector.BANKING,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=12000000, typical_spread_bps=3,
                       notes="Largest public sector bank")

        self._add_stock("AXISBANK", "Axis Bank", Sector.BANKING,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=7000000, typical_spread_bps=3)

        self._add_stock("KOTAKBANK", "Kotak Mahindra Bank", Sector.BANKING,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=4000000, typical_spread_bps=3)

        # Energy Sector
        self._add_stock("RELIANCE", "Reliance Industries", Sector.ENERGY,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=15000000, typical_spread_bps=1,
                       notes="Oil refining and petrochemicals giant")

        self._add_stock("ONGC", "Oil and Natural Gas Corporation", Sector.ENERGY,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=10000000, typical_spread_bps=4,
                       notes="Government oil exploration")

        self._add_stock("BPCL", "Bharat Petroleum Corporation", Sector.ENERGY,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=3000000, typical_spread_bps=6)

        # FMCG Sector
        self._add_stock("HINDUNILVR", "Hindustan Unilever", Sector.FMCG,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=2000000, typical_spread_bps=3,
                       notes="FMCG leader, defensive stock")

        self._add_stock("ITC", "ITC Limited", Sector.FMCG,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=8000000, typical_spread_bps=2,
                       notes="Tobacco and FMCG conglomerate")

        self._add_stock("NESTLEIND", "Nestle India", Sector.FMCG,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=500000, typical_spread_bps=8)

        # Telecom Sector
        self._add_stock("BHARTIARTL", "Bharti Airtel", Sector.TELECOM,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=6000000, typical_spread_bps=3,
                       notes="Leading telecom operator")

        # Infrastructure Sector
        self._add_stock("LT", "Larsen & Toubro", Sector.INFRASTRUCTURE,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=3000000, typical_spread_bps=4,
                       notes="Engineering and construction")

        self._add_stock("ULTRACEMCO", "UltraTech Cement", Sector.INFRASTRUCTURE,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=1500000, typical_spread_bps=6)

        # Auto Sector
        self._add_stock("MARUTI", "Maruti Suzuki", Sector.AUTO,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=2500000, typical_spread_bps=4,
                       notes="Leading car manufacturer")

        self._add_stock("TATAMOTORS", "Tata Motors", Sector.AUTO,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=8000000, typical_spread_bps=5)

        # Pharma Sector
        self._add_stock("SUNPHARMA", "Sun Pharmaceutical", Sector.PHARMA,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=3000000, typical_spread_bps=4)

        self._add_stock("DRREDDY", "Dr. Reddy's Laboratories", Sector.PHARMA,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=1500000, typical_spread_bps=6)

        # Metals Sector
        self._add_stock("TATASTEEL", "Tata Steel", Sector.METALS,
                       MarketCap.LARGE_CAP, LiquidityRating.HIGH, True,
                       avg_daily_volume=6000000, typical_spread_bps=5,
                       notes="Cyclical stock, commodity exposure")

        self._add_stock("HINDALCO", "Hindalco Industries", Sector.METALS,
                       MarketCap.LARGE_CAP, LiquidityRating.MEDIUM, True,
                       avg_daily_volume=4000000, typical_spread_bps=6)

    def _add_stock(self, symbol: str, company_name: str, sector: Sector,
                   market_cap: MarketCap, liquidity: LiquidityRating,
                   is_index_stock: bool = False, is_active: bool = True,
                   avg_daily_volume: Optional[int] = None,
                   typical_spread_bps: Optional[int] = None,
                   notes: Optional[str] = None):
        """Add a stock to the registry"""
        self.stocks[symbol] = StockInfo(
            symbol=symbol,
            company_name=company_name,
            sector=sector,
            market_cap=market_cap,
            liquidity=liquidity,
            is_index_stock=is_index_stock,
            is_active=is_active,
            avg_daily_volume=avg_daily_volume,
            typical_spread_bps=typical_spread_bps,
            notes=notes
        )

    def get_all_symbols(self, active_only: bool = True) -> List[str]:
        """Get all stock symbols"""
        if active_only:
            return [symbol for symbol, info in self.stocks.items() if info.is_active]
        return list(self.stocks.keys())

    def get_symbols_by_sector(self, sector: Sector, active_only: bool = True) -> List[str]:
        """Get symbols filtered by sector"""
        return [
            symbol for symbol, info in self.stocks.items()
            if info.sector == sector and (not active_only or info.is_active)
        ]

    def get_conservative_portfolio(self, max_symbols: int = 10) -> List[str]:
        """
        Get conservative portfolio symbols.

        Criteria: Large cap, high liquidity, index stocks, defensive sectors
        """
        conservative_symbols = []

        # Priority 1: Banking and Technology (defensive)
        for sector in [Sector.BANKING, Sector.TECHNOLOGY, Sector.FMCG]:
            sector_symbols = [
                symbol for symbol, info in self.stocks.items()
                if (info.sector == sector and
                    info.market_cap == MarketCap.LARGE_CAP and
                    info.liquidity == LiquidityRating.HIGH and
                    info.is_index_stock and
                    info.is_active)
            ]
            conservative_symbols.extend(sector_symbols[:3])  # Max 3 per sector

        return conservative_symbols[:max_symbols]

    def get_swing_trading_symbols(self, max_symbols: int = 8) -> List[str]:
        """
        Get symbols optimized for swing trading.

        Criteria: High liquidity, good volatility, tight spreads
        """
        swing_symbols = [
            symbol for symbol, info in self.stocks.items()
            if (info.liquidity == LiquidityRating.HIGH and
                info.typical_spread_bps and info.typical_spread_bps <= 5 and
                info.avg_daily_volume and info.avg_daily_volume >= MIN_LIQUIDITY_VOLUME and
                info.is_active)
        ]

        # Sort by liquidity metrics (volume and spread)
        swing_symbols.sort(key=lambda s: (
            -self.stocks[s].avg_daily_volume,  # Higher volume first
            self.stocks[s].typical_spread_bps   # Lower spread first
        ))

        return swing_symbols[:max_symbols]

    def get_diversified_portfolio(self, max_symbols: int = 10) -> List[str]:
        """
        Get a diversified portfolio across sectors.

        Ensures representation from different sectors and market caps.
        """
        diversified = []
        sectors_covered = set()

        # Prioritize high-liquidity stocks from different sectors
        high_liquidity_stocks = [
            (symbol, info) for symbol, info in self.stocks.items()
            if info.liquidity == LiquidityRating.HIGH and info.is_active
        ]

        # Sort by sector to ensure diversity
        for symbol, info in high_liquidity_stocks:
            if len(diversified) >= max_symbols:
                break

            if info.sector not in sectors_covered:
                diversified.append(symbol)
                sectors_covered.add(info.sector)

        # Fill remaining slots with best remaining stocks
        remaining_stocks = [
            symbol for symbol in self.get_all_symbols()
            if symbol not in diversified and self.stocks[symbol].liquidity != LiquidityRating.LOW
        ]

        diversified.extend(remaining_stocks[:max_symbols - len(diversified)])

        return diversified[:max_symbols]

    def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get detailed information for a specific stock"""
        return self.stocks.get(symbol.upper())

# Global registry instance
_stock_registry = None

def get_stock_registry() -> StockRegistry:
    """Get the global stock registry instance"""
    global _stock_registry
    if _stock_registry is None:
        _stock_registry = StockRegistry()
    return _stock_registry


# Convenience wrappers around the global registry
def get_conservative_symbols(max_symbols: int = 10) -> List[str]:
    """Get conservative trading symbols"""
    return get_stock_registry().get_conservative_portfolio(max_symbols)

def get_swing_trading_symbols(max_symbols: int = 8) -> List[str]:
    """Get symbols optimized for swing trading"""
    return get_stock_registry().get_swing_trading_symbols(max_symbols)

def get_diversified_symbols(max_symbols: int = 10) -> List[str]:
    """Get diversified portfolio symbols"""
    return get_stock_registry().get_diversified_portfolio(max_symbols)

def get_symbols_by_sector(sector_name: str) -> List[str]:
    """Get symbols by sector name (accepts a Sector enum or its string value)."""
    try:
        # Handle both enum and string inputs
        if isinstance(sector_name, str):
            sector = Sector(sector_name.lower())
        else:
            sector = sector_name
        return get_stock_registry().get_symbols_by_sector(sector)
    except ValueError:
        # If sector name not found, return empty list
        return []


