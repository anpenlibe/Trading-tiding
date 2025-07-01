"""
Module: stock_registry.py
Purpose: Centralized stock management with sector organization and metadata
Author: Trading Bot Developer
Created: 2025-06-30
Modified: 2025-07-01 - FIXED: Sector filtering and import issues

This module provides centralized stock symbol management with:
- Sector-based organization
- Market cap and liquidity information  
- Trading priority and risk classification
- Easy symbol selection for different strategies

FIXES APPLIED:
- Fixed sector filtering (was returning empty for tech)
- Fixed import path issues
- Improved symbol selection logic
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum
import json
import os


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
    
    def get_symbols_by_market_cap(self, market_cap: MarketCap, active_only: bool = True) -> List[str]:
        """Get symbols filtered by market cap"""
        return [
            symbol for symbol, info in self.stocks.items()
            if info.market_cap == market_cap and (not active_only or info.is_active)
        ]
    
    def get_symbols_by_liquidity(self, liquidity: LiquidityRating, active_only: bool = True) -> List[str]:
        """Get symbols filtered by liquidity rating"""
        return [
            symbol for symbol, info in self.stocks.items()
            if info.liquidity == liquidity and (not active_only or info.is_active)
        ]
    
    def get_index_stocks(self, active_only: bool = True) -> List[str]:
        """Get symbols that are part of major indices"""
        return [
            symbol for symbol, info in self.stocks.items()
            if info.is_index_stock and (not active_only or info.is_active)
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
    
    def get_aggressive_portfolio(self, max_symbols: int = 10) -> List[str]:
        """
        Get aggressive portfolio symbols.
        
        Criteria: Include cyclical sectors, mixed market caps
        """
        aggressive_symbols = []
        
        # Include cyclical and growth sectors
        growth_sectors = [Sector.TECHNOLOGY, Sector.AUTO, Sector.METALS, Sector.ENERGY]
        
        for sector in growth_sectors:
            sector_symbols = [
                symbol for symbol, info in self.stocks.items()
                if (info.sector == sector and 
                    info.liquidity in [LiquidityRating.HIGH, LiquidityRating.MEDIUM] and
                    info.is_active)
            ]
            aggressive_symbols.extend(sector_symbols[:3])
        
        return aggressive_symbols[:max_symbols]
    
    def get_swing_trading_symbols(self, max_symbols: int = 8) -> List[str]:
        """
        Get symbols optimized for swing trading.
        
        Criteria: High liquidity, good volatility, tight spreads
        """
        swing_symbols = [
            symbol for symbol, info in self.stocks.items()
            if (info.liquidity == LiquidityRating.HIGH and
                info.typical_spread_bps and info.typical_spread_bps <= 5 and
                info.avg_daily_volume and info.avg_daily_volume >= 2000000 and
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
    
    def get_sector_summary(self) -> Dict[Sector, Dict[str, int]]:
        """Get summary statistics by sector"""
        summary = {}
        
        for sector in Sector:
            sector_stocks = [info for info in self.stocks.values() if info.sector == sector and info.is_active]
            
            summary[sector] = {
                'total_stocks': len(sector_stocks),
                'large_cap': len([s for s in sector_stocks if s.market_cap == MarketCap.LARGE_CAP]),
                'high_liquidity': len([s for s in sector_stocks if s.liquidity == LiquidityRating.HIGH]),
                'index_stocks': len([s for s in sector_stocks if s.is_index_stock])
            }
        
        return summary
    
    def save_to_file(self, filepath: str):
        """Save the registry to a JSON file"""
        data = {}
        for symbol, info in self.stocks.items():
            data[symbol] = {
                'company_name': info.company_name,
                'sector': info.sector.value,
                'market_cap': info.market_cap.value,
                'liquidity': info.liquidity.value,
                'is_index_stock': info.is_index_stock,
                'is_active': info.is_active,
                'avg_daily_volume': info.avg_daily_volume,
                'typical_spread_bps': info.typical_spread_bps,
                'notes': info.notes
            }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_file(self, filepath: str):
        """Load the registry from a JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.stocks.clear()
        for symbol, stock_data in data.items():
            self._add_stock(
                symbol=symbol,
                company_name=stock_data['company_name'],
                sector=Sector(stock_data['sector']),
                market_cap=MarketCap(stock_data['market_cap']),
                liquidity=LiquidityRating(stock_data['liquidity']),
                is_index_stock=stock_data['is_index_stock'],
                is_active=stock_data['is_active'],
                avg_daily_volume=stock_data.get('avg_daily_volume'),
                typical_spread_bps=stock_data.get('typical_spread_bps'),
                notes=stock_data.get('notes')
            )


# Global registry instance
_stock_registry = None

def get_stock_registry() -> StockRegistry:
    """Get the global stock registry instance"""
    global _stock_registry
    if _stock_registry is None:
        _stock_registry = StockRegistry()
    return _stock_registry


# FIXED: Convenience functions with proper sector handling
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
    """Get symbols by sector name - FIXED VERSION"""
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


if __name__ == "__main__":
    # Test the stock registry
    registry = get_stock_registry()
    
    print("🏢 Stock Registry - Indian Market")
    print("=" * 50)
    
    print(f"\nTotal Stocks: {len(registry.get_all_symbols())}")
    
    print("\n📊 Conservative Portfolio:")
    conservative = registry.get_conservative_portfolio(8)
    for symbol in conservative:
        info = registry.get_stock_info(symbol)
        print(f"  {symbol} - {info.company_name} ({info.sector.value})")
    
    print("\n⚡ Swing Trading Symbols:")
    swing = registry.get_swing_trading_symbols(6)
    for symbol in swing:
        info = registry.get_stock_info(symbol)
        print(f"  {symbol} - Vol: {info.avg_daily_volume:,}, Spread: {info.typical_spread_bps}bps")
    
    print("\n🌐 Diversified Portfolio:")
    diversified = registry.get_diversified_portfolio(10)
    for symbol in diversified:
        info = registry.get_stock_info(symbol)
        print(f"  {symbol} - {info.sector.value.title()}")
    
    print("\n💻 Technology Sector:")
    tech_symbols = get_symbols_by_sector("technology")
    for symbol in tech_symbols:
        info = registry.get_stock_info(symbol)
        print(f"  {symbol} - {info.company_name}")
    
    print("\n📈 Sector Summary:")
    summary = registry.get_sector_summary()
    for sector, stats in summary.items():
        if stats['total_stocks'] > 0:
            print(f"  {sector.value.title()}: {stats['total_stocks']} stocks, {stats['high_liquidity']} high-liquidity")
