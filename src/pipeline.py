"""Shared trading pipeline: decision → risk → execution for one set of bars.

Mode-agnostic. A runner (backtest now, live later) gathers the current portfolio
bars + indicators via its feed, then calls ``run_decisions(...)`` here. Only
ingestion and timing differ between modes; this decide→risk→execute body is
identical, so it lives once. The risk manager and executor are injected (paper
executor now, a live executor later), and either may be ``None`` (decide-only).
"""

from typing import Dict, Any, List, Optional

from src.platform.logger import setup_logger
from src.platform.events import log_event
from src.platform.config import MIN_ACT_CONFIDENCE, REGIME_BREADTH_MIN
from src.features.indicators import summarize_market_regime

logger = setup_logger(__name__, 'pipeline.log')

# Verbs that act on an EXISTING holding — skip them when we don't hold the symbol.
# BUY is the only verb that opens fresh (and risk rejects it if we already hold).
_REQUIRES_POSITION = {'SELL', 'TRIM', 'MOVE_STOP', 'ADD'}

# Verbs that OPEN or INCREASE risk — gated by the confidence floor AND the regime gate.
# Exits and risk-reducing/protective moves (SELL, TRIM, MOVE_STOP) are NEVER gated.
_FLOOR_GATED = {'BUY', 'ADD'}
_ENTRY_VERBS = {'BUY', 'ADD'}


def _entries_allowed(portfolio_indicators) -> bool:
    """Regime gate: allow new longs only when market breadth is constructive. A weak/
    bearish tape (few stocks above SMA50) is where momentum entries get chopped up, so
    BUY/ADD are blocked there — the AI can still manage/exit. Defaults to ALLOW when
    breadth can't be assessed (don't silently block everything on a data gap)."""
    regime = summarize_market_regime(portfolio_indicators or {})
    pct = regime.get('pct_above_sma50') if regime else None
    if pct is None:
        return True
    return pct >= REGIME_BREADTH_MIN * 100


class TradingPipeline:
    """Runs the decide→risk→execute body of one trading tick over a portfolio."""

    def __init__(self, brain, risk_manager=None, executor=None):
        self.brain = brain
        self.risk_manager = risk_manager
        self.executor = executor

    def _apply_thesis(self, symbol: str, decision: Dict[str, Any]) -> None:
        """Persist an evolving thesis/status from a decision onto a HELD position, so the
        next pass sees the updated view even when the decision itself is a HOLD (which
        never reaches the executor). No-op if we don't hold the symbol or nothing changed."""
        if self.executor is None or not self.executor.has_position(symbol):
            return
        thesis = decision.get('thesis')
        status = decision.get('thesis_status')
        if thesis or status:
            self.executor.update_thesis(symbol, thesis=thesis, status=status)

    def run_decisions(self, portfolio_data: Dict[str, Any],
                      portfolio_indicators: Dict[str, Dict[str, float]],
                      current_prices: Dict[str, float],
                      context: Dict[str, Any]) -> Dict[str, Any]:
        """Get portfolio AI decisions, then risk-validate + execute each non-HOLD.

        Returns ``{'decisions': {...}, 'market_analysis': str, 'executed': [...]}``
        where each executed entry is ``{'symbol', 'decision', 'price', 'result'}``.
        """
        result = self.brain.analyze_portfolio_with_intelligent_fallback(
            portfolio_data, portfolio_indicators, context
        )
        decisions = result.get('decisions', {})
        market_analysis = result.get('market_analysis', '')

        executed = self._execute_batch(decisions, current_prices, portfolio_indicators,
                                       _entries_allowed(portfolio_indicators))
        return {'decisions': decisions, 'market_analysis': market_analysis, 'executed': executed}

    def _execute_batch(self, decisions: Dict[str, Any], current_prices: Dict[str, float],
                       portfolio_indicators: Dict[str, Dict[str, float]],
                       entries_allowed: bool) -> List[Dict[str, Any]]:
        """Apply a batch of per-symbol decisions: persist evolving thesis, gate (regime
        for entries, position for manage verbs), then risk-validate + execute each
        non-HOLD. Shared by the general pass and the consolidated alert review.
        ``entries_allowed`` is the regime verdict, computed by the caller over the FULL
        universe (not the reviewed subset, which would mismeasure breadth)."""
        executed: List[Dict[str, Any]] = []
        if self.executor is None:
            return executed
        for symbol, decision in decisions.items():
            if symbol not in current_prices:
                continue
            # Persist any evolving thesis/status onto a held position first — this must
            # happen even for a HOLD (which doesn't execute below).
            self._apply_thesis(symbol, decision)
            signal_type = decision.get('signal')
            if not signal_type or signal_type == 'HOLD':
                continue
            # Regime gate: no new longs in a weak-breadth tape (manage/exit only).
            if signal_type in _ENTRY_VERBS and not entries_allowed:
                logger.info(f"Regime gate: skip {signal_type} {symbol} - weak market breadth")
                log_event('skipped', symbol=symbol, signal=signal_type, reason='weak_regime')
                continue
            # Can't act on a holding we don't have (the AI sometimes emits
            # SELL/TRIM/ADD/MOVE_STOP for an unowned symbol).
            if signal_type in _REQUIRES_POSITION and not self.executor.has_position(symbol):
                logger.info(f"Skipping {signal_type} for {symbol} - no position held")
                continue

            atr = (portfolio_indicators.get(symbol) or {}).get('atr_14')
            trade_result = self._execute(symbol, decision, current_prices[symbol], atr=atr)
            if trade_result.get('status') == 'EXECUTED':
                executed.append({
                    'symbol': symbol, 'decision': decision,
                    'price': current_prices[symbol], 'result': trade_result,
                })
        return executed

    def run_alert_review(self, portfolio_data: Dict[str, Any],
                         portfolio_indicators: Dict[str, Dict[str, float]],
                         current_prices: Dict[str, float], context: Dict[str, Any],
                         owned_symbols: List[str], candidate_symbols: List[str],
                         regime_indicators: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Any]:
        """Consolidated mid-cycle ALERT review (replaces the per-symbol special-pass
        fan-out): ONE prompt over open positions (recheck + manage) ∪ surfaced candidates
        (consider, skeptically) → one AI call → gate + execute the batch. Same action
        contract as the general pass, so it reuses ``_execute_batch``. ``regime_indicators``
        is the FULL-universe indicator set for the breadth/regime gate (the reviewed subset
        alone would mismeasure breadth); falls back to the reviewed set if not given."""
        result = self.brain.analyze_alert_review(
            portfolio_data, portfolio_indicators, owned_symbols, candidate_symbols, context
        )
        decisions = result.get('decisions', {})
        entries_allowed = _entries_allowed(regime_indicators or portfolio_indicators)
        executed = self._execute_batch(decisions, current_prices, portfolio_indicators, entries_allowed)
        return {'decisions': decisions, 'market_analysis': result.get('market_analysis', ''),
                'executed': executed}

    def manage_positions(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Per-tick mechanical position management: mark to market and fire the
        stop-loss / target SAFETY FLOOR.

        This runs every tick in BOTH modes (the shared-core guarantee), beneath the
        AI/alert layer: the alert rules wake the AI as price *approaches* a level so
        it gets first say, and this guarantees the exit if price actually reaches the
        hard level and the AI didn't act. Returns the auto-closed fills so a runner
        can log/record them and refresh derived state. No-op without an executor."""
        if self.executor is None:
            return []
        return self.executor.update_positions(current_prices)

    def _execute(self, symbol: str, signal: Dict[str, Any], current_price: float,
                 atr: Optional[float] = None) -> Dict[str, Any]:
        """Risk-validate + size + execute one signal at ``current_price``.

        ``atr`` (the symbol's ATR(14), when available) makes the risk manager scale
        stops/targets to the stock's own volatility instead of a flat percentage.

        Execution layers its own fields (sized position, ATR stops, slippage-adjusted
        entry) onto a COPY of the signal, so the caller's decision dict keeps the AI's
        original values — the executed parameters travel back via the returned fill,
        not by mutating shared state."""
        try:
            order = dict(signal)
            order['symbol'] = symbol

            # Confidence floor (single choke point, honored by every caller): a BUY/ADD
            # below MIN_ACT_CONFIDENCE is not worth opening/adding risk on — skip it.
            # SELL/TRIM/MOVE_STOP are never gated (exits/protection must always run).
            if order.get('signal') in _FLOOR_GATED:
                confidence = order.get('confidence') or 0.0
                if confidence < MIN_ACT_CONFIDENCE:
                    logger.info(f"Floor gate: skip {order.get('signal')} {symbol} - "
                                f"confidence {confidence:.2f} < {MIN_ACT_CONFIDENCE}")
                    log_event('skipped', symbol=symbol, signal=order.get('signal'),
                              confidence=round(float(confidence), 3), reason='below_confidence_floor')
                    return {'status': 'SKIPPED', 'reason': 'below_confidence_floor'}

            # The fill happens at the current market price; stamp it so risk sizing
            # doesn't crash on a missing entry_price (otherwise swallowed as a
            # silent non-execution).
            if order.get('entry_price') is None:
                order['entry_price'] = current_price

            if self.risk_manager is not None:
                account_info = self.executor.get_account_info()
                order['available_capital'] = account_info['available_capital']

                is_valid, rejection_reason, risk_params = self.risk_manager.validate_trade(
                    order, self.executor.get_positions(), atr=atr
                )
                if not is_valid:
                    return {'status': 'REJECTED', 'reason': rejection_reason}

                # validate_trade already sized this exact trade — ATR-scaled when ATR
                # is present (the single-symbol prompt leaves stop_loss/target null
                # precisely because the system applies ATR levels), the AI's templated
                # ±% ignored. Reuse its result rather than recomputing; a second
                # compute could silently drift from what was actually validated.
                # risk_params is None for a SELL (a full close needs no sizing).
                if risk_params is not None:
                    order.update({
                        'position_size': risk_params.position_size,
                        'stop_loss': risk_params.stop_loss,
                        'target': risk_params.target,
                        'entry_price': risk_params.entry_price,
                        'risk_amount': risk_params.risk_amount,
                    })

            return self.executor.execute_trade(order, current_price)

        except Exception as e:
            logger.debug(f"Trade execution error for {symbol}: {e}")
            return {'status': 'ERROR', 'message': str(e)}
