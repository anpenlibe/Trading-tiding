"""Custom exceptions for the trading system."""

class TradingSystemError(Exception):
    """Base exception for all trading system errors."""
    pass

class DataCollectionError(TradingSystemError):
    """Raised when data collection fails."""
    pass

class ValidationError(TradingSystemError):
    """Raised when data validation fails."""
    pass

class AIAnalysisError(TradingSystemError):
    """Raised when AI analysis fails."""
    pass

class RiskValidationError(TradingSystemError):
    """Raised when risk validation fails."""
    pass

class TradeExecutionError(TradingSystemError):
    """Raised when trade execution fails."""
    pass

class DatabaseError(TradingSystemError):
    """Raised when database operations fail."""
    pass

class ConfigurationError(TradingSystemError):
    """Raised when configuration is invalid."""
    pass

class APIError(TradingSystemError):
    """Raised when external API calls fail."""
    def __init__(self, message, api_name=None, status_code=None):
        super().__init__(message)
        self.api_name = api_name
        self.status_code = status_code