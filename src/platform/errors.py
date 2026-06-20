"""Custom exception hierarchy for the trading system.

Every error derives from TradingSystemError, so a caller can catch the whole
family with a single ``except TradingSystemError``. Only exceptions that are
actually raised somewhere live here; see tests/test_exceptions.py for the
ones removed during cleanup.
"""


class TradingSystemError(Exception):
    """Base exception for all trading system errors."""


class DataCollectionError(TradingSystemError):
    """Raised when market-data collection fails."""


class ValidationError(TradingSystemError):
    """Raised when data validation fails."""


class AIAnalysisError(TradingSystemError):
    """Raised when AI analysis fails (e.g. all providers exhausted)."""


class DatabaseError(TradingSystemError):
    """Raised when database operations fail."""


class ConfigurationError(TradingSystemError):
    """Raised when configuration is invalid."""
