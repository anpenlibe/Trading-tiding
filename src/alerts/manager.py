"""Alert manager — bridges the AlertEngine to the trading loop.

Registers default technical rules per symbol (RSI extreme, MACD cross, volume
spike) plus DYNAMIC rules the AI emits each general pass (``alert_conditions``:
price_above / price_below). Each tick the loop calls ``evaluate(snapshots)`` to
get the symbols whose alerts fired; the runner then runs the single-symbol SPECIAL
pass for each — the notes' "monitor between cycles, deep-dive on a trigger".

Note: AlertRule cooldowns are wall-clock based (designed for live). In a fast
backtest, sim-time != wall-clock, so a rule fires roughly once per run. That's a
known limitation of backtesting the alert layer, not a correctness bug.
"""

from typing import Dict, Any, List

from src.alerts.engine import AlertEngine
from src.alerts.rules import RSIExtremeRule, MACDCrossRule, VolumeSpikRule, PriceCrossRule
from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'alerts.log')


class AlertManager:
    """Holds the alert rules and evaluates them against per-symbol snapshots."""

    def __init__(self, symbols: List[str]):
        self.engine = AlertEngine()
        self._dynamic_names: set = set()  # AI-emitted rule names (refreshed each general pass)
        for s in symbols:
            self.engine.add_rule(RSIExtremeRule(s))
            self.engine.add_rule(MACDCrossRule(s, "bullish"))
            self.engine.add_rule(MACDCrossRule(s, "bearish"))
            self.engine.add_rule(VolumeSpikRule(s))
        logger.info(f"AlertManager: {len(self.engine.alert_rules)} default rules for {len(symbols)} symbols")

    def register_ai_conditions(self, decisions: Dict[str, Dict[str, Any]]):
        """Replace the AI-emitted price rules with the latest general-pass output."""
        # Drop the previous batch of dynamic rules, keep the static technical ones.
        self.engine.alert_rules = [r for r in self.engine.alert_rules if r.name not in self._dynamic_names]
        self._dynamic_names.clear()

        for symbol, dec in decisions.items():
            cond = dec.get('alert_conditions') if isinstance(dec, dict) else None
            if not isinstance(cond, dict):
                continue
            for field, direction in (("price_above", "above"), ("price_below", "below")):
                level = cond.get(field)
                if level:
                    try:
                        rule = PriceCrossRule(symbol, float(level), direction)
                    except (TypeError, ValueError):
                        continue
                    self.engine.add_rule(rule)
                    self._dynamic_names.add(rule.name)

    def evaluate(self, snapshots: Dict[str, Dict[str, Any]]) -> List[str]:
        """Return the distinct symbols whose alert rules fired this tick.

        ``snapshots[symbol]`` must carry ``close``, ``volume`` and ``indicators``.
        """
        triggered: set = set()
        for symbol, snap in snapshots.items():
            market_data = {"symbol": symbol, **snap}
            for alert in self.engine.check_conditions(market_data):
                triggered.add(alert.symbol)
                logger.info(f"ALERT {alert.type.value} on {alert.symbol} "
                            f"(value={alert.current_value}, threshold={alert.threshold})")
        return list(triggered)
