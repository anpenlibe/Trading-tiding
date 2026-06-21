"""Smart alert system for event-driven trading."""

from dataclasses import dataclass
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from src.platform.config import RSI_OVERBOUGHT, RSI_OVERSOLD
from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'alerts.log')


class AlertType(Enum):
    PRICE_CROSS = "price_cross"
    RSI_EXTREME = "rsi_extreme"
    VOLUME_SPIKE = "volume_spike"
    MACD_CROSS = "macd_cross"
    PATTERN = "pattern"
    PORTFOLIO = "portfolio"


@dataclass
class Alert:
    """Alert data structure."""
    alert_id: str
    type: AlertType
    symbol: str
    condition: str
    threshold: float
    current_value: float
    triggered_at: datetime
    priority: int  # 1=high, 5=low
    metadata: Dict[str, Any]


class AlertEngine:
    """Core alert engine."""
    
    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_rules: List['AlertRule'] = []
        self.cooldowns: Dict[str, datetime] = {}
        self.callbacks: Dict[AlertType, List[Callable]] = {}
        
    def add_rule(self, rule: 'AlertRule'):
        """Add alert rule."""
        self.alert_rules.append(rule)
        logger.info(f"Added rule: {rule.name}")
    
    def register_callback(self, alert_type: AlertType, callback: Callable):
        """Register callback for alert type."""
        if alert_type not in self.callbacks:
            self.callbacks[alert_type] = []
        self.callbacks[alert_type].append(callback)
    
    def check_conditions(self, market_data: Dict[str, Any],
                         now: Optional[datetime] = None) -> List[Alert]:
        """Check all alert conditions.

        ``now`` is the reference clock for cooldowns. Live passes nothing (defaults
        to wall-clock); the backtest passes the current SIM timestamp so cooldowns
        advance with market time instead of real time — otherwise a fast replay
        burns the whole run inside one wall-clock cooldown and each rule fires once.
        """
        now = now or datetime.now()
        triggered_alerts = []

        for rule in self.alert_rules:
            # Check cooldown
            if self._in_cooldown(rule.name, now):
                continue

            # Check condition
            if rule.check(market_data):
                alert = self._create_alert(rule, market_data, now)
                triggered_alerts.append(alert)
                self._trigger_alert(alert)

                # Set cooldown
                self.cooldowns[rule.name] = now + timedelta(minutes=rule.cooldown_minutes)

        return triggered_alerts
    
    def _trigger_alert(self, alert: Alert):
        """Execute callbacks for triggered alert."""
        callbacks = self.callbacks.get(alert.type, [])
        for callback in callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Callback failed: {e}")
    
    def _in_cooldown(self, rule_name: str, now: datetime) -> bool:
        """Check if rule is in cooldown as of ``now``."""
        if rule_name in self.cooldowns:
            return now < self.cooldowns[rule_name]
        return False

    def _create_alert(self, rule: 'AlertRule', market_data: Dict[str, Any],
                      now: datetime) -> Alert:
        """Create alert from triggered rule, stamped at ``now``."""
        return Alert(
            alert_id=f"{rule.name}_{now.timestamp()}",
            type=rule.alert_type,
            symbol=market_data.get('symbol', 'UNKNOWN'),
            condition=rule.condition,
            threshold=rule.threshold,
            current_value=rule.get_current_value(market_data),
            triggered_at=now,
            priority=rule.priority,
            metadata=rule.get_metadata(market_data)
        )


class AlertRule:
    """Base class for alert rules."""
    
    def __init__(self, name: str, alert_type: AlertType, 
                 condition: str, threshold: float,
                 priority: int = 3, cooldown_minutes: int = 30):
        self.name = name
        self.alert_type = alert_type
        self.condition = condition
        self.threshold = threshold
        self.priority = priority
        self.cooldown_minutes = cooldown_minutes
    
    def check(self, market_data: Dict[str, Any]) -> bool:
        """Check if condition is met."""
        raise NotImplementedError
    
    def get_current_value(self, market_data: Dict[str, Any]) -> float:
        """Get current value being checked."""
        raise NotImplementedError
    
    def get_metadata(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get additional metadata."""
        return {}