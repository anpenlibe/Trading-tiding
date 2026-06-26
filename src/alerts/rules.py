"""Predefined alert rules."""

from typing import Dict, Any
from src.alerts.engine import AlertRule, AlertType
from src.platform.config import (
    RSI_OVERBOUGHT, RSI_OVERSOLD, VOLUME_SMA_PERIOD, VOLUME_SPIKE_MULTIPLIER,
    MACD_CROSS_MIN_GAP_PCT, MACD_CROSS_COOLDOWN_MIN,
    RSI_PULLBACK_MAX, SUPPORT_BAND_PCT,
)


# ---- candidate SURFACING rules (mean-reversion in an uptrend) ----------------------
# These look for DIPS worth a closer look in STRONG names — not momentum breakouts. They
# are stateless predicates (no cross-detection): they fire whenever the condition currently
# holds, so a name keeps surfacing for consideration while it stays interesting. cooldown 0
# (the alert layer re-evaluates each tick; the consolidated review decides whether to act).

class OversoldPullbackRule(AlertRule):
    """Surface a dip in an uptrend: RSI <= pullback threshold WHILE price is above SMA50.

    The uptrend filter (price > SMA50) is what separates 'buy the dip in a strong name'
    from 'catch a falling knife' — oversold alone, in a downtrend, is not interesting."""

    def __init__(self, symbol: str, rsi_max: float = RSI_PULLBACK_MAX):
        super().__init__(name=f"{symbol}_oversold_pullback",
                         alert_type=AlertType.RSI_EXTREME, condition="oversold_pullback",
                         threshold=rsi_max, priority=2, cooldown_minutes=0)
        self.symbol = symbol
        self.rsi_max = rsi_max

    def check(self, market_data: Dict[str, Any]) -> bool:
        if market_data.get('symbol') != self.symbol:
            return False
        ind = market_data.get('indicators', {})
        rsi = ind.get('rsi_14')
        sma50 = ind.get('sma_50')
        price = market_data.get('close', 0)
        if rsi is None or sma50 is None or not price:
            return False
        return rsi <= self.rsi_max and price > sma50

    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        return market_data.get('indicators', {}).get('rsi_14', 50)


class SupportPullbackRule(AlertRule):
    """Surface a pullback to moving-average support: price has come back to within
    SUPPORT_BAND_PCT of SMA20 or SMA50 FROM ABOVE (was trading above it) — a trend-pullback
    entry zone, not a breakdown."""

    def __init__(self, symbol: str, band_pct: float = SUPPORT_BAND_PCT):
        super().__init__(name=f"{symbol}_support_pullback",
                         alert_type=AlertType.PRICE_CROSS, condition="support_pullback",
                         threshold=band_pct, priority=2, cooldown_minutes=0)
        self.symbol = symbol
        self.band = band_pct / 100.0

    def check(self, market_data: Dict[str, Any]) -> bool:
        if market_data.get('symbol') != self.symbol:
            return False
        ind = market_data.get('indicators', {})
        price = market_data.get('close', 0)
        if not price:
            return False
        for ma in (ind.get('sma_20'), ind.get('sma_50')):
            if ma and price >= ma and (price - ma) / ma <= self.band:
                return True  # at-or-just-above a rising MA = support test
        return False

    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        return market_data.get('close', 0)


class PriceCrossRule(AlertRule):
    """Alert when price crosses a threshold.

    ``kind`` labels WHY the level matters so the fired alert is self-describing in
    the special-pass prompt: ``approaching_stop`` / ``approaching_target`` /
    ``recheck`` (AI position-management levels) vs the default ``price_above`` /
    ``price_below`` (a level the AI explicitly asked to watch). It also keeps the
    rule name unique so two different levels on the same symbol don't collide.
    """

    def __init__(self, symbol: str, threshold: float, direction: str = "above",
                 kind: str = None, priority: int = 2):
        condition = kind or f"price_{direction}"
        super().__init__(
            name=f"{symbol}_{condition}_{threshold}",
            alert_type=AlertType.PRICE_CROSS,
            condition=condition,
            threshold=threshold,
            priority=priority
        )
        self.symbol = symbol
        self.direction = direction
        self.last_price = None
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        if market_data.get('symbol') != self.symbol:
            return False
        
        current_price = market_data.get('close', 0)
        
        if self.last_price is None:
            self.last_price = current_price
            return False
        
        # Check for crossover
        if self.direction == "above":
            triggered = self.last_price <= self.threshold < current_price
        else:
            triggered = self.last_price >= self.threshold > current_price
        
        self.last_price = current_price
        return triggered
    
    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        return market_data.get('close', 0)


class RSIExtremeRule(AlertRule):
    """Alert on RSI extremes."""
    
    def __init__(self, symbol: str, overbought: float = RSI_OVERBOUGHT, 
                 oversold: float = RSI_OVERSOLD):
        super().__init__(
            name=f"{symbol}_rsi_extreme",
            alert_type=AlertType.RSI_EXTREME,
            condition="rsi_extreme",
            threshold=0,  # Will use overbought/oversold
            priority=1,
            cooldown_minutes=60
        )
        self.symbol = symbol
        self.overbought = overbought
        self.oversold = oversold
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        if market_data.get('symbol') != self.symbol:
            return False
        
        rsi = market_data.get('indicators', {}).get('rsi_14', 50)
        return rsi >= self.overbought or rsi <= self.oversold
    
    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        return market_data.get('indicators', {}).get('rsi_14', 50)
    
    def get_metadata(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        rsi = self.get_current_value(market_data)
        return {
            'rsi_value': rsi,
            'overbought_threshold': self.overbought,
            'oversold_threshold': self.oversold,
            'condition': 'overbought' if rsi >= self.overbought else 'oversold'
        }


class VolumeSpikRule(AlertRule):
    """Alert on volume spikes."""
    
    def __init__(self, symbol: str, spike_multiplier: float = VOLUME_SPIKE_MULTIPLIER):
        super().__init__(
            name=f"{symbol}_volume_spike",
            alert_type=AlertType.VOLUME_SPIKE,
            condition="volume_spike",
            threshold=spike_multiplier,
            priority=3
        )
        self.symbol = symbol
        self.volume_history = []
        self.history_size = VOLUME_SMA_PERIOD
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        if market_data.get('symbol') != self.symbol:
            return False
        
        current_volume = market_data.get('volume', 0)
        self.volume_history.append(current_volume)
        
        if len(self.volume_history) > self.history_size:
            self.volume_history.pop(0)
        
        if len(self.volume_history) < self.history_size:
            return False
        
        avg_volume = sum(self.volume_history[:-1]) / (len(self.volume_history) - 1)
        return current_volume > avg_volume * self.threshold
    
    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        return market_data.get('volume', 0)
    
    def get_metadata(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        current_volume = self.get_current_value(market_data)
        avg_volume = sum(self.volume_history[:-1]) / max(len(self.volume_history) - 1, 1) if len(self.volume_history) > 1 else 0
        return {
            'current_volume': current_volume,
            'average_volume': avg_volume,
            'spike_ratio': current_volume / max(avg_volume, 1),
            'threshold_multiplier': self.threshold
        }


class MACDCrossRule(AlertRule):
    """Alert on MACD signal-line crossovers — but only *meaningful* ones.

    A bare sign-flip of (macd - signal) is noise on 1-minute data: the lines hug
    zero and cross back and forth on tiny wiggles. We require the lines to have
    actually separated — ``|macd - signal| >= min_gap_pct% of price`` — so a
    hair-thin zero-line whipsaw doesn't wake the special pass into a reflexive
    trade. Price-relative so the bar scales across cheap and expensive stocks.
    """

    def __init__(self, symbol: str, direction: str = "bullish",
                 min_gap_pct: float = MACD_CROSS_MIN_GAP_PCT,
                 cooldown_minutes: int = MACD_CROSS_COOLDOWN_MIN):
        super().__init__(
            name=f"{symbol}_macd_{direction}_cross",
            alert_type=AlertType.MACD_CROSS,
            condition=f"macd_{direction}_cross",
            threshold=0,
            priority=2,
            cooldown_minutes=cooldown_minutes
        )
        self.symbol = symbol
        self.direction = direction  # "bullish" or "bearish"
        self.min_gap_pct = min_gap_pct
        self.last_macd = None
        self.last_signal = None

    def check(self, market_data: Dict[str, Any]) -> bool:
        if market_data.get('symbol') != self.symbol:
            return False

        indicators = market_data.get('indicators', {})
        current_macd = indicators.get('macd', 0)
        current_signal = indicators.get('macd_signal', 0)

        if self.last_macd is None or self.last_signal is None:
            self.last_macd = current_macd
            self.last_signal = current_signal
            return False

        # Check for crossover
        if self.direction == "bullish":
            # MACD crosses above signal
            triggered = (self.last_macd <= self.last_signal and
                        current_macd > current_signal)
        else:
            # MACD crosses below signal
            triggered = (self.last_macd >= self.last_signal and
                        current_macd < current_signal)

        # Gate on real separation: ignore near-zero micro-crosses (the whipsaw).
        if triggered:
            price = market_data.get('close', 0) or 0
            min_gap = (self.min_gap_pct / 100.0) * price
            if abs(current_macd - current_signal) < min_gap:
                triggered = False

        self.last_macd = current_macd
        self.last_signal = current_signal
        return triggered
    
    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        indicators = market_data.get('indicators', {})
        macd = indicators.get('macd', 0)
        signal = indicators.get('macd_signal', 0)
        return macd - signal  # MACD histogram
    
    def get_metadata(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', {})
        return {
            'macd': indicators.get('macd', 0),
            'signal': indicators.get('macd_signal', 0),
            'histogram': indicators.get('macd_histogram', 0),
            'crossover_direction': self.direction
        }


