"""Technical indicator calculations — the Features layer.

``calculate_all_indicators(df)`` is the single entry point used across the
pipeline (data_collector, trader, backtest, health_check): it turns an OHLCV
DataFrame into a flat dict of the latest indicator values — RSI, MACD (+ signal
+ histogram), SMAs (from config.SMA_PERIODS), a volume SMA, and price-change %.
The individual ``calculate_*`` helpers are the building blocks and are
independently testable. Each returns ``None`` when its own minimum window isn't
met, so partial data degrades gracefully instead of raising.
"""

import warnings
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.data.config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    SMA_PERIODS, VOLUME_SMA_PERIOD,
)

warnings.filterwarnings("ignore")  # silence pandas/numpy edge-case warnings


def calculate_sma(data: pd.Series, period: int) -> Optional[float]:
    """Simple Moving Average over `period`, or None if too few points."""
    if len(data) >= period:
        return float(data.rolling(window=period).mean().iloc[-1])
    return None


def calculate_rsi(data: pd.Series, period: int = RSI_PERIOD) -> Optional[float]:
    """Relative Strength Index over `period`, or None if too few points."""
    if len(data) < period + 1:
        return None

    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else None


def calculate_macd(data: pd.Series, fast: int = MACD_FAST, slow: int = MACD_SLOW,
                   signal: int = MACD_SIGNAL) -> Dict[str, Optional[float]]:
    """MACD line, signal line, and histogram; all None if too few points."""
    if len(data) < slow:
        return {'macd': None, 'macd_signal': None, 'macd_histogram': None}

    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    def last(series):
        return float(series.iloc[-1]) if not np.isnan(series.iloc[-1]) else None

    return {
        'macd': last(macd_line),
        'macd_signal': last(signal_line),
        'macd_histogram': last(histogram),
    }


def calculate_price_change_pct(data: pd.Series) -> Optional[float]:
    """Percent change of the latest close vs the previous one, or None."""
    if len(data) >= 2:
        return float(((data.iloc[-1] - data.iloc[-2]) / data.iloc[-2]) * 100)
    return None


def calculate_all_indicators(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Compute all indicators for the latest row of an OHLCV DataFrame.

    Returns an empty dict when there are fewer than 5 rows; otherwise a dict of
    indicator name -> latest value (individual values may be None if their own
    window isn't met).
    """
    if df is None or len(df) < 5:
        return {}

    close = df["close"]
    macd = calculate_macd(close)  # computed once (previously recomputed 3x)

    result = {
        "rsi_14": calculate_rsi(close, RSI_PERIOD),
        "macd": macd["macd"],
        "macd_signal": macd["macd_signal"],
        "macd_histogram": macd["macd_histogram"],
    }
    for period in SMA_PERIODS:
        result[f"sma_{period}"] = calculate_sma(close, period)
    if "volume" in df.columns:
        result["volume_avg_20"] = calculate_sma(df["volume"], VOLUME_SMA_PERIOD)
    result["price_change_pct"] = calculate_price_change_pct(close)
    return result
