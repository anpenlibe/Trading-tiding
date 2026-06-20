"""Predefined alert rules."""

from typing import Dict, Any
from src.alerts.engine import AlertRule, AlertType
from src.platform.config import RSI_OVERBOUGHT, RSI_OVERSOLD, VOLUME_SMA_PERIOD


class PriceCrossRule(AlertRule):
    """Alert when price crosses threshold."""
    
    def __init__(self, symbol: str, threshold: float, direction: str = "above"):
        super().__init__(
            name=f"{symbol}_price_{direction}_{threshold}",
            alert_type=AlertType.PRICE_CROSS,
            condition=f"price_{direction}",
            threshold=threshold,
            priority=2
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
    
    def __init__(self, symbol: str, spike_multiplier: float = 2.0):
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
    """Alert on MACD signal line crossovers."""
    
    def __init__(self, symbol: str, direction: str = "bullish"):
        super().__init__(
            name=f"{symbol}_macd_{direction}_cross",
            alert_type=AlertType.MACD_CROSS,
            condition=f"macd_{direction}_cross",
            threshold=0,
            priority=2,
            cooldown_minutes=45
        )
        self.symbol = symbol
        self.direction = direction  # "bullish" or "bearish"
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


