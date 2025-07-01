"""
Module: indicator_engine.py
Purpose: Unified technical indicator calculations for the trading bot
Author: Trading Bot Developer
Created: 2025-06-13
Modified: 2025-06-30 - Enhanced with complete indicator set, now single source of truth
"""

import pandas as pd
import numpy as np
import warnings
from typing import Dict, Optional, List, Any

warnings.filterwarnings("ignore")  # Clean output


def compute_indicators(df: pd.DataFrame, indicators: List[str] = None) -> Dict[str, float]:
    """
    Computes a dictionary of indicator values for the latest row in df.
    df should have columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    Args:
        df: DataFrame with OHLCV data
        indicators: List of indicators to compute. If None, computes all available.
    
    Returns:
        Dict of indicator_name -> value for the latest data point
    """
    result = {}

    if df is None or len(df) < 5:
        return result  # Not enough data

    close = df["close"]
    volume = df["volume"] if "volume" in df.columns else None
    
    # Default to all indicators if none specified
    if indicators is None:
        indicators = [
            "rsi_14", "macd", "macd_signal", "macd_histogram",
            "sma_20", "sma_50", "sma_200", 
            "volume_avg_20", "price_change_pct"
        ]
    
    for ind in indicators:
        try:
            if ind == "rsi" or ind == "rsi_14":
                result["rsi_14"] = calculate_rsi(close, 14)
            elif ind == "macd":
                macd_values = calculate_macd(close)
                result["macd"] = macd_values.get("macd")
            elif ind == "macd_signal":
                macd_values = calculate_macd(close)
                result["macd_signal"] = macd_values.get("macd_signal") 
            elif ind == "macd_histogram":
                macd_values = calculate_macd(close)
                result["macd_histogram"] = macd_values.get("macd_histogram")
            elif ind.startswith("sma_"):
                period = int(ind.split("_")[1])
                result[ind] = calculate_sma(close, period)
            elif ind == "volume_avg_20" and volume is not None:
                result[ind] = calculate_sma(volume, 20)
            elif ind == "price_change_pct":
                result[ind] = calculate_price_change_pct(close)
            # Add more indicators here as needed
        except Exception:
            result[ind] = None  # Safe fallback
    
    return result


def calculate_sma(data: pd.Series, period: int) -> Optional[float]:
    """Calculate Simple Moving Average"""
    if len(data) >= period:
        return float(data.rolling(window=period).mean().iloc[-1])
    return None


def calculate_rsi(data: pd.Series, period: int = 14) -> Optional[float]:
    """Calculate Relative Strength Index"""
    if len(data) < period + 1:
        return None
    
    # Calculate price changes
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Calculate RS and RSI
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else None


def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, 
                  signal: int = 9) -> Dict[str, Optional[float]]:
    """Calculate MACD indicator with all components"""
    if len(data) < slow:
        return {'macd': None, 'macd_signal': None, 'macd_histogram': None}
    
    # Calculate exponential moving averages
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    
    # Calculate MACD line
    macd_line = ema_fast - ema_slow
    
    # Calculate signal line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    # Calculate histogram
    histogram = macd_line - signal_line
    
    return {
        'macd': float(macd_line.iloc[-1]) if not np.isnan(macd_line.iloc[-1]) else None,
        'macd_signal': float(signal_line.iloc[-1]) if not np.isnan(signal_line.iloc[-1]) else None,
        'macd_histogram': float(histogram.iloc[-1]) if not np.isnan(histogram.iloc[-1]) else None
    }


def calculate_price_change_pct(data: pd.Series) -> Optional[float]:
    """Calculate price change percentage from previous period"""
    if len(data) >= 2:
        return float(
            ((data.iloc[-1] - data.iloc[-2]) / data.iloc[-2]) * 100
        )
    return None


def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate all available indicators for the latest data point.
    This is the main function that should be used by data collectors.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Dict of all calculated indicators
    """
    return compute_indicators(df)


# Legacy function names for backward compatibility during transition
def _rsi(series: pd.Series, period: int = 14) -> float:
    """Legacy RSI function - use calculate_rsi instead"""
    result = calculate_rsi(series, period)
    return result if result is not None else 0.0


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> float:
    """Legacy MACD function - use calculate_macd instead"""
    result = calculate_macd(series, fast, slow, signal)
    return result.get('macd_histogram', 0.0) if result.get('macd_histogram') is not None else 0.0
