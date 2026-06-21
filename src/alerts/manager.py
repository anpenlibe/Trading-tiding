"""Alert manager — turns the AI's intent + the live book into the wake signals
that drive the special pass.

The two-pass design wants the alert layer to be the AI's nervous system, not a
blanket technical scanner. So rules are built from three sources, scoped to the
symbols the AI actually cares about (OWNED ∪ WATCHLIST) — idle stocks are
reconsidered at the next general pass, not via noisy intraday special passes:

  1. POSITION MANAGEMENT (owned): wake the AI *before* its hard stop/target — a
     price-cross a hair inside each level (``approaching_stop`` / ``approaching_target``)
     plus a recheck band at entry ± the AI's ``recheck_trigger_pct``. This is the
     "manage the holding" loop: the executor still auto-closes at the exact level
     as a safety floor, but the AI gets first say.
  2. WATCH LEVELS: the AI's ``alert_conditions`` (price_above / price_below) — the
     entry levels it asked to be woken on.
  3. TECHNICAL BACKSTOP: RSI-extreme / MACD-cross / volume-spike, on WATCH stocks
     ONLY (never holdings) — a catch for interesting behavior worth an entry look,
     not a trigger to dump a position on indicator noise.

Each general pass calls ``update_from_general(decisions, positions)``; after a
special pass changes the book, the runner calls ``refresh(positions)`` so a newly
opened/closed position gets (or loses) its management rules immediately.

Note: AlertRule cooldowns are wall-clock based (designed for live). In a fast
backtest, sim-time != wall-clock, so a rule fires roughly once per run. That's a
known limitation of backtesting the alert layer, not a correctness bug.
"""

from typing import Dict, Any, List, Optional

from src.alerts.engine import AlertEngine
from src.alerts.rules import RSIExtremeRule, MACDCrossRule, VolumeSpikRule, PriceCrossRule
from src.platform.config import ALERT_APPROACH_FRACTION, EMERGENCY_RECHECK_PCT
from src.platform.logger import setup_logger
from src.platform.events import log_event

logger = setup_logger(__name__, 'alerts.log')


def _f(value) -> Optional[float]:
    """Best-effort float, or None for missing/garbage (keeps level math safe)."""
    try:
        f = float(value)
        return f if f == f else None  # reject NaN
    except (TypeError, ValueError):
        return None


class AlertManager:
    """Builds alert rules from the AI's intent + the book; evaluates them per tick."""

    def __init__(self, symbols: List[str]):
        self.symbols = list(symbols)
        self.engine = AlertEngine()
        # Rule instances are reused across rebuilds by name, so stateful rules
        # (volume history, last MACD/price for cross detection) survive a resync.
        self._rules_by_name: Dict[str, Any] = {}
        # Cached from the most recent general pass, replayed on mid-cycle refreshes.
        self._watchlist: set = set()
        self._ai_conditions: Dict[str, dict] = {}
        logger.info(f"AlertManager initialized for {len(self.symbols)} symbols "
                    f"(rules scoped to owned + watchlist)")

    def update_from_general(self, decisions: Dict[str, Dict[str, Any]],
                            positions: Dict[str, Any]):
        """Refresh the watchlist + AI watch-levels from a general pass, then rebuild."""
        self._watchlist = {s for s, d in decisions.items()
                           if isinstance(d, dict) and d.get('watchlist')}
        self._ai_conditions = {s: d['alert_conditions'] for s, d in decisions.items()
                               if isinstance(d, dict) and isinstance(d.get('alert_conditions'), dict)}
        self._rebuild(positions)

    def refresh(self, positions: Dict[str, Any]):
        """Rebuild after the book changes mid-cycle (special-pass fill), reusing the
        last general pass's watchlist/watch-levels."""
        self._rebuild(positions)

    # Backwards-compatible alias (older call sites passed only decisions).
    def register_ai_conditions(self, decisions: Dict[str, Dict[str, Any]]):
        self.update_from_general(decisions, positions={})

    def _rebuild(self, positions: Optional[Dict[str, Any]]):
        positions = positions or {}
        owned = set(positions)
        active = owned | self._watchlist

        # Collect the rules we WANT this cycle, reusing existing instances by name.
        # Technical rules (RSI/MACD/volume) run on WATCH stocks only — never on
        # holdings. A raw indicator twitch is an entry-hunting signal, not a reason
        # to dump a position; owned stocks are exited only by their position levels
        # (approach stop/target, recheck) or the scheduled general pass. This stops
        # the de-noise whack-a-mole where silencing one rule promotes the next.
        wanted: List[Any] = []
        wanted += self._technical_rules(self._watchlist - owned)
        wanted += self._watch_level_rules(active)
        wanted += self._position_rules(positions)

        new_by_name: Dict[str, Any] = {}
        for rule in wanted:
            new_by_name[rule.name] = self._rules_by_name.get(rule.name, rule)
        self._rules_by_name = new_by_name
        self.engine.alert_rules = list(new_by_name.values())

        logger.info(f"Alert rules rebuilt: {len(self.engine.alert_rules)} rules over "
                    f"{len(active)} watched symbols (owned {sorted(owned)}, "
                    f"watchlist {sorted(self._watchlist)})")

    def _technical_rules(self, watch_only: set) -> List[Any]:
        """RSI/MACD/volume backstop — WATCH stocks only (never holdings), so a raw
        indicator can flag an entry but can't manufacture an exit."""
        rules: List[Any] = []
        for s in sorted(watch_only):
            rules.append(RSIExtremeRule(s))
            rules.append(MACDCrossRule(s, "bullish"))
            rules.append(MACDCrossRule(s, "bearish"))
            rules.append(VolumeSpikRule(s))
        return rules

    def _watch_level_rules(self, active: set) -> List[Any]:
        """Price levels the AI explicitly asked to be woken on (entry watching)."""
        rules: List[Any] = []
        for s, cond in self._ai_conditions.items():
            if s not in active:
                continue
            for field, direction in (("price_above", "above"), ("price_below", "below")):
                level = _f(cond.get(field))
                if level:
                    rules.append(PriceCrossRule(s, level, direction))
        return rules

    def _position_rules(self, positions: Dict[str, Any]) -> List[Any]:
        """Wake-the-AI levels for held stocks: approach the hard stop/target, and a
        recheck band at entry ± the AI's recheck %. Fires BEFORE the executor's
        mechanical auto-close so the AI gets to manage the position first.

        The approach level is anchored to the entry→level DISTANCE (``frac`` of the
        way there), not a flat % of the level — a flat % overshoots past entry on a
        tight ATR stop and would fire the instant you enter."""
        rules: List[Any] = []
        frac = ALERT_APPROACH_FRACTION
        for s, p in positions.items():
            stop = _f(p.get('stop_loss'))
            target = _f(p.get('target'))
            entry = _f(p.get('entry_price'))
            # Approach alerts need a sane entry with the level on the right side.
            if entry and stop and stop < entry:
                # Wake when price has fallen `frac` of the way from entry to stop.
                level = entry - frac * (entry - stop)
                rules.append(PriceCrossRule(s, level, "below",
                                            kind="approaching_stop", priority=1))
            if entry and target and target > entry:
                # Wake when price has risen `frac` of the way from entry to target.
                level = entry + frac * (target - entry)
                rules.append(PriceCrossRule(s, level, "above",
                                            kind="approaching_target", priority=1))
            if entry:
                rpct = abs(_f(p.get('emergency_recheck_pct')) or EMERGENCY_RECHECK_PCT) / 100.0
                if rpct:
                    rules.append(PriceCrossRule(s, entry * (1 + rpct), "above", kind="recheck"))
                    rules.append(PriceCrossRule(s, entry * (1 - rpct), "below", kind="recheck"))
        return rules

    def evaluate(self, snapshots: Dict[str, Dict[str, Any]], now=None) -> Dict[str, List[Dict[str, Any]]]:
        """Return ``{symbol: [fired-alert, ...]}`` for symbols whose rules fired.

        Each fired-alert is ``{type, value, threshold, condition}`` — the REASON the
        symbol tripped, so the runner can hand it to the special-pass prompt (the AI
        is told *why* it's being woken, not just that it is). Iterating the result
        still yields the symbols, so callers that loop ``for s in triggered`` work.

        ``snapshots[symbol]`` must carry ``close``, ``volume`` and ``indicators``.
        ``now`` is the cooldown clock — backtest passes the sim timestamp; live
        leaves it None (wall-clock).
        """
        triggered: Dict[str, List[Dict[str, Any]]] = {}
        for symbol, snap in snapshots.items():
            market_data = {"symbol": symbol, **snap}
            for alert in self.engine.check_conditions(market_data, now=now):
                logger.info(f"ALERT {alert.condition} on {alert.symbol} "
                            f"(value={alert.current_value}, threshold={alert.threshold})")
                log_event('alert', atype=alert.type.value, condition=alert.condition,
                          symbol=alert.symbol, value=alert.current_value,
                          threshold=alert.threshold,
                          sim_time=str(now) if now is not None else None)
                triggered.setdefault(alert.symbol, []).append({
                    'type': alert.type.value, 'value': alert.current_value,
                    'threshold': alert.threshold, 'condition': alert.condition,
                })
        return triggered
