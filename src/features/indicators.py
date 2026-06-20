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

from src.platform.config import (
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
    """Relative Strength Index over `period` using Wilder's smoothing, or None
    if too few points.

    Wilder smooths average gain/loss with an EMA of alpha=1/period — the standard
    used by TradingView and most TA libraries. The previous simple-rolling-mean
    ("Cutler's RSI") variant ran several points hotter (e.g. 79.8 vs a standard
    71 on the same data), which miscalibrated the conventional 70/30 thresholds.
    """
    if len(data) < period + 1:
        return None

    delta = data.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    last = rsi.iloc[-1]
    return float(last) if not np.isnan(last) else None


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


# ----- Tier-1 features (per the notes): volatility, bands, volume flow, momentum
# trajectory, trend state. Each returns None when its own window isn't met. -----

def calculate_atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Average True Range (Wilder's smoothing) — per-stock volatility for sizing
    stops/targets. None if too few bars."""
    if df is None or len(df) < period + 1 or not {"high", "low", "close"} <= set(df.columns):
        return None
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().iloc[-1]
    return float(atr) if not np.isnan(atr) else None


def calculate_bollinger(close: pd.Series, period: int = 20, num_std: float = 2.0):
    """(%B, bandwidth%) — %B is position within the bands (0=lower, 1=upper);
    bandwidth is band width as % of the middle band (volatility). (None, None) if short."""
    if len(close) < period:
        return None, None
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper, lower = mid + num_std * std, mid - num_std * std
    u, l, m, c = upper.iloc[-1], lower.iloc[-1], mid.iloc[-1], close.iloc[-1]
    if np.isnan(u) or (u - l) == 0:
        return None, None
    pct_b = float((c - l) / (u - l))
    bandwidth = float((u - l) / m * 100) if m else None
    return pct_b, bandwidth


def calculate_obv_trend(df: pd.DataFrame, lookback: int = 10) -> Optional[float]:
    """Normalized OBV momentum ~[-1, 1] (+ accumulation / - distribution): net OBV
    change over `lookback` bars divided by volume traded in that window. None if short."""
    if "volume" not in df.columns or len(df) < lookback + 1:
        return None
    direction = np.sign(df["close"].diff().fillna(0))
    obv = (direction * df["volume"]).cumsum()
    recent_vol = df["volume"].iloc[-lookback:].sum()
    if recent_vol == 0:
        return 0.0
    return float((obv.iloc[-1] - obv.iloc[-lookback - 1]) / recent_vol)


def calculate_rsi_trajectory(close: pd.Series, period: int = RSI_PERIOD, lookback: int = 3) -> Optional[float]:
    """Change in RSI over the last `lookback` bars (>0 rising, <0 falling). None if short."""
    if len(close) < period + lookback + 1:
        return None
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rsi = 100 - (100 / (1 + avg_gain / avg_loss))
    now, prev = rsi.iloc[-1], rsi.iloc[-1 - lookback]
    if np.isnan(now) or np.isnan(prev):
        return None
    return float(now - prev)


def calculate_macd_cross(close: pd.Series, fast: int = MACD_FAST, slow: int = MACD_SLOW,
                         signal: int = MACD_SIGNAL) -> Dict[str, Optional[float]]:
    """MACD-vs-signal state: ``macd_cross`` (+1 bullish cross this bar, -1 bearish, 0 none)
    and ``macd_above_signal`` (1/0)."""
    if len(close) < slow + signal:
        return {"macd_cross": None, "macd_above_signal": None}
    macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = macd_line.ewm(span=signal, adjust=False).mean()
    above_now = macd_line.iloc[-1] > sig.iloc[-1]
    above_prev = macd_line.iloc[-2] > sig.iloc[-2]
    cross = 1.0 if (above_now and not above_prev) else (-1.0 if (above_prev and not above_now) else 0.0)
    return {"macd_cross": cross, "macd_above_signal": 1.0 if above_now else 0.0}


def calculate_price_vs_sma_pct(close: pd.Series, period: int) -> Optional[float]:
    """Latest close as a % above/below its SMA(`period`) — overextension / trend. None if short."""
    sma = calculate_sma(close, period)
    if sma is None or sma == 0:
        return None
    return float((close.iloc[-1] - sma) / sma * 100)


# ----- Tier-3 features (momentum / overextension / volume) ------------------------

def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    """Stochastic %K and %D (0-100): where close sits in the recent high-low range,
    smoothed. (None, None) if short."""
    if len(df) < k_period + d_period or not {"high", "low", "close"} <= set(df.columns):
        return None, None
    low_min = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    kv, dv = k.iloc[-1], d.iloc[-1]
    return (float(kv) if not np.isnan(kv) else None, float(dv) if not np.isnan(dv) else None)


def calculate_roc(close: pd.Series, period: int = 10) -> Optional[float]:
    """Rate of Change %: close vs `period` bars ago. None if short."""
    if len(close) < period + 1:
        return None
    prev = close.iloc[-1 - period]
    return float((close.iloc[-1] - prev) / prev * 100) if prev else None


def calculate_range_position(df: pd.DataFrame, period: int = 20) -> Optional[float]:
    """Where close sits in the N-bar high-low range: 0 = period low, 1 = period high
    (overextension signal). None if short."""
    if len(df) < period or not {"high", "low", "close"} <= set(df.columns):
        return None
    hi = df["high"].iloc[-period:].max()
    lo = df["low"].iloc[-period:].min()
    return float((df["close"].iloc[-1] - lo) / (hi - lo)) if hi != lo else None


def calculate_volume_trend(df: pd.DataFrame, short: int = 5, long: int = 20) -> Optional[float]:
    """Recent avg volume vs longer avg (>1 = volume rising into the move). None if short."""
    if "volume" not in df.columns or len(df) < long:
        return None
    long_avg = df["volume"].iloc[-long:].mean()
    return float(df["volume"].iloc[-short:].mean() / long_avg) if long_avg else None


def summarize_market_regime(portfolio_indicators: Dict[str, Dict[str, float]],
                            index_symbol: str = "^NSEI") -> Dict[str, object]:
    """Market-wide regime from per-symbol indicators — breadth-based (works without
    index data), enriched with the index's own trend if its indicators are present.

    Returns ``{regime, avg_rsi, pct_above_sma50, breadth_n, [index_rsi, index_vs_sma50_pct]}``
    or ``{}`` if there's nothing to summarize.
    """
    rsis = [i.get("rsi_14") for i in portfolio_indicators.values() if i.get("rsi_14") is not None]
    above = [i.get("price_vs_sma50_pct") for i in portfolio_indicators.values()
             if i.get("price_vs_sma50_pct") is not None]
    if not rsis:
        return {}
    avg_rsi = sum(rsis) / len(rsis)
    pct_above = (sum(1 for x in above if x > 0) / len(above) * 100) if above else None
    if avg_rsi >= 55 and (pct_above or 0) >= 60:
        label = "bullish"
    elif avg_rsi <= 45 and (pct_above if pct_above is not None else 100) <= 40:
        label = "bearish"
    else:
        label = "neutral"
    out: Dict[str, object] = {
        "regime": label,
        "avg_rsi": round(avg_rsi, 1),
        "pct_above_sma50": round(pct_above) if pct_above is not None else None,
        "breadth_n": len(rsis),
    }
    idx = portfolio_indicators.get(index_symbol)
    if idx:
        out["index_rsi"] = idx.get("rsi_14")
        out["index_vs_sma50_pct"] = idx.get("price_vs_sma50_pct")
    return out


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

    # Tier-1 features
    result["atr_14"] = calculate_atr(df, 14)
    pct_b, bandwidth = calculate_bollinger(close, 20)
    result["bollinger_pct_b"] = pct_b
    result["bollinger_bandwidth"] = bandwidth
    result["obv_trend"] = calculate_obv_trend(df, 10)
    result["rsi_trajectory"] = calculate_rsi_trajectory(close, RSI_PERIOD, 3)
    cross = calculate_macd_cross(close)
    result["macd_cross"] = cross["macd_cross"]
    result["macd_above_signal"] = cross["macd_above_signal"]
    result["price_vs_sma20_pct"] = calculate_price_vs_sma_pct(close, 20)
    result["price_vs_sma50_pct"] = calculate_price_vs_sma_pct(close, 50)

    # Tier-3 features
    stoch_k, stoch_d = calculate_stochastic(df, 14, 3)
    result["stoch_k"] = stoch_k
    result["stoch_d"] = stoch_d
    result["roc_10"] = calculate_roc(close, 10)
    result["range_position"] = calculate_range_position(df, 20)
    result["volume_trend"] = calculate_volume_trend(df, 5, 20)
    return result
