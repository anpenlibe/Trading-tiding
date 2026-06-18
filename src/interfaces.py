"""Core data structures and abstract interfaces shared across the pipeline.

``MarketData`` is the canonical OHLCV record passed between the data, indicator,
decision, risk, and execution layers. The ``Base*`` ABCs define the contracts
each layer's concrete classes implement:

    ZerodhaAPI / YahooFinanceAPI / MockAPI -> BaseMarketDataAPI
    AIBrain                                -> BaseDecisionModel
    SimpleRiskManager                      -> BaseRiskManager
    PaperTrader                            -> BaseTradingExecutor
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from dataclasses import dataclass

import pandas as pd


@dataclass
class MarketData:
    """A single OHLCV bar for one symbol at one point in time."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (timestamp as ISO-8601)."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(timespec="microseconds"),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'source': self.source,
        }


class BaseMarketDataAPI(ABC):
    """Contract for a market-data source (Zerodha, Yahoo, Mock)."""

    @abstractmethod
    def __init__(self, **kwargs):
        """Initialize with any necessary credentials."""

    @abstractmethod
    def fetch_ohlc(self, symbol: str) -> Optional[MarketData]:
        """Fetch the latest OHLC bar for ``symbol``, or None on failure."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the source is configured and reachable."""

    def get_name(self) -> str:
        """Human-readable source name (defaults to the class name)."""
        return self.__class__.__name__


class BaseDecisionModel(ABC):
    """Contract for a model that turns market data + indicators into a signal."""

    @abstractmethod
    def analyze(self, market_data: pd.DataFrame, indicators: Dict[str, float]) -> Dict[str, Any]:
        """Return a decision dict with signal (BUY/SELL/HOLD), confidence,
        reasoning, and optional stop_loss / target."""

    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """Indicators this model needs computed before analyze()."""


class BaseRiskManager(ABC):
    """Contract for position sizing and trade validation."""

    @abstractmethod
    def calculate_position_size(self, capital: float, risk_per_trade: float,
                                stop_loss_distance: float, entry_price: float = None) -> int:
        """Position size (shares) for the given risk parameters."""

    @abstractmethod
    def validate_trade(self, signal: Dict[str, Any],
                       current_positions: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a trade against the risk rules.

        Returns ``(is_valid, reason)`` where ``reason`` explains a rejection
        (None when valid).
        """


class BaseTradingExecutor(ABC):
    """Contract for trade execution and account/position queries."""

    @abstractmethod
    def place_order(self, symbol: str, quantity: int, order_type: str,
                    price: Optional[float] = None) -> Dict[str, Any]:
        """Place an order and return a result dict."""

    @abstractmethod
    def get_positions(self) -> Dict[str, Any]:
        """Current open positions."""

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Account summary (capital, returns, etc.)."""
