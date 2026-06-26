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
from src.alerts.rules import OversoldPullbackRule, SupportPullbackRule, PriceCrossRule
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
        # Per-symbol watch REASON (the AI's intent: "want a pullback to ~3150"), carried
        # into the next general prompt so a watch candidate is re-evaluated against why
        # it was flagged — not re-rated blind. The wake LEVELS live in _ai_conditions.
        self._watchlist_reason: Dict[str, str] = {}
        logger.info(f"AlertManager initialized for {len(self.symbols)} symbols "
                    f"(rules scoped to owned + watchlist)")

    def update_from_general(self, decisions: Dict[str, Dict[str, Any]],
                            positions: Dict[str, Any]):
        """Refresh the watchlist + AI watch-levels from a general pass, then rebuild."""
        self._watchlist = {s for s, d in decisions.items()
                           if isinstance(d, dict) and d.get('watchlist')}
        self._ai_conditions = {s: d['alert_conditions'] for s, d in decisions.items()
                               if isinstance(d, dict) and isinstance(d.get('alert_conditions'), dict)}
        self._watchlist_reason = {s: d.get('watchlist_reason') for s, d in decisions.items()
                                  if isinstance(d, dict) and d.get('watchlist') and d.get('watchlist_reason')}
        self._rebuild(positions)

    # ----- watchlist intent: carried into the NEXT general prompt (memory) -----

    def get_watchlist_symbols(self) -> List[str]:
        """The standing watchlist (symbols the AI asked to keep tracking)."""
        return sorted(self._watchlist)

    def get_watchlist_intent(self) -> Dict[str, Dict[str, Any]]:
        """{symbol: {reason, conditions}} for each watched symbol — the AI's prior
        intent, so the next general pass re-evaluates against it instead of blind."""
        return {s: {'reason': self._watchlist_reason.get(s),
                    'conditions': self._ai_conditions.get(s)}
                for s in self._watchlist}

    def seed_watchlist_intent(self, intent: Dict[str, Dict[str, Any]],
                              positions: Optional[Dict[str, Any]] = None):
        """Restore persisted watchlist intent (e.g. a live restart) and rebuild rules so
        the standing watchlist survives across sessions rather than starting empty."""
        if not intent:
            return
        self._watchlist = set(intent.keys())
        self._watchlist_reason = {s: v.get('reason') for s, v in intent.items() if v.get('reason')}
        self._ai_conditions = {s: v['conditions'] for s, v in intent.items()
                               if isinstance(v.get('conditions'), dict)}
        self._rebuild(positions or {})

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
        # Two sources, both on WATCH candidates (never holdings): (1) mean-reversion
        # SURFACING (dips in strong names worth a closer look), (2) the AI's own price
        # levels. Position management is NOT a rule anymore — the consolidated alert
        # review rechecks every open position unconditionally, so approach-stop/target/
        # recheck rules are redundant (and were the churn source).
        wanted: List[Any] = []
        wanted += self._surfacing_rules(self._watchlist - owned)
        wanted += self._watch_level_rules(active)

        new_by_name: Dict[str, Any] = {}
        for rule in wanted:
            new_by_name[rule.name] = self._rules_by_name.get(rule.name, rule)
        self._rules_by_name = new_by_name
        self.engine.alert_rules = list(new_by_name.values())

        logger.info(f"Alert rules rebuilt: {len(self.engine.alert_rules)} rules over "
                    f"{len(active)} watched symbols (owned {sorted(owned)}, "
                    f"watchlist {sorted(self._watchlist)})")

    def _surfacing_rules(self, watch_only: set) -> List[Any]:
        """Mean-reversion-in-trend surfacing — WATCH candidates only. Looks for DIPS in
        strong names (oversold-while-above-SMA50, pullback-to-MA-support) worth a closer
        look, NOT momentum breakouts. Surfaces for CONSIDERATION; the review decides."""
        rules: List[Any] = []
        for s in sorted(watch_only):
            rules.append(OversoldPullbackRule(s))
            rules.append(SupportPullbackRule(s))
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
