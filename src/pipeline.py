"""Shared trading pipeline: decision → risk → execution for one set of bars.

Mode-agnostic. A runner (backtest now, live later) gathers the current portfolio
bars + indicators via its feed, then calls ``run_decisions(...)`` here. Only
ingestion and timing differ between modes; this decide→risk→execute body is
identical, so it lives once. The risk manager and executor are injected (paper
executor now, a live executor later), and either may be ``None`` (decide-only).
"""

from typing import Dict, Any, List, Optional

from src.platform.logger import setup_logger

logger = setup_logger(__name__, 'pipeline.log')


class TradingPipeline:
    """Runs the decide→risk→execute body of one trading tick over a portfolio."""

    def __init__(self, brain, risk_manager=None, executor=None):
        self.brain = brain
        self.risk_manager = risk_manager
        self.executor = executor

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

        executed: List[Dict[str, Any]] = []
        if self.executor is not None:
            for symbol, decision in decisions.items():
                if symbol not in current_prices:
                    continue
                signal_type = decision.get('signal')
                if signal_type == 'HOLD':
                    continue
                # Can't sell what we don't hold (the AI sometimes emits SELL for unowned).
                if signal_type == 'SELL' and not self.executor.has_position(symbol):
                    logger.info(f"Skipping SELL for {symbol} - no position held")
                    continue

                atr = (portfolio_indicators.get(symbol) or {}).get('atr_14')
                trade_result = self._execute(symbol, decision, current_prices[symbol], atr=atr)
                if trade_result.get('status') == 'EXECUTED':
                    executed.append({
                        'symbol': symbol, 'decision': decision,
                        'price': current_prices[symbol], 'result': trade_result,
                    })

        return {'decisions': decisions, 'market_analysis': market_analysis, 'executed': executed}

    def run_special(self, symbol: str, market_data, indicators: Dict[str, float],
                    current_price: float, alert_context=None) -> Dict[str, Any]:
        """Alert-triggered SPECIAL pass: a single-symbol deep analysis (short prompt
        → the fast gpt-oss symbol chain) → risk → execute. ``alert_context`` is the
        list of fired alerts (why this symbol tripped), passed into the prompt so the
        model acts on the trigger. Returns ``{'symbol', 'decision', 'executed'}``."""
        # If we hold this symbol, hand the model its position so it can manage it
        # (trim/hold/exit) instead of re-rating as if flat.
        position = self.executor.get_positions().get(symbol) if self.executor is not None else None
        decision = self.brain.analyze(market_data, indicators,
                                      alert_context=alert_context, position=position)
        signal_type = decision.get('signal')
        executed = None
        if signal_type and signal_type != 'HOLD' and self.executor is not None:
            if signal_type == 'SELL' and not self.executor.has_position(symbol):
                logger.info(f"Special pass: skip SELL for {symbol} - no position held")
            else:
                executed = self._execute(symbol, decision, current_price,
                                         atr=(indicators or {}).get('atr_14'))
        return {'symbol': symbol, 'decision': decision, 'executed': executed}

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
        stops/targets to the stock's own volatility instead of a flat percentage."""
        try:
            # The fill happens at the current market price; stamp it on the signal
            # so risk sizing doesn't crash on a missing entry_price (otherwise
            # swallowed as a silent non-execution).
            if signal.get('entry_price') is None:
                signal['entry_price'] = current_price

            if self.risk_manager is not None:
                account_info = self.executor.get_account_info()
                signal['available_capital'] = account_info['available_capital']

                is_valid, rejection_reason = self.risk_manager.validate_trade(
                    signal, self.executor.get_positions(), atr=atr
                )
                if not is_valid:
                    return {'status': 'REJECTED', 'reason': rejection_reason}

                # When ATR is available, let it set volatility-scaled stops/targets
                # rather than the AI's templated levels — the single-symbol prompt
                # tells the model to echo entry*0.985 / entry*1.03, so its stop is
                # boilerplate, not a considered level. ATR adapts per stock instead.
                stop_in = None if atr else signal.get('stop_loss')
                target_in = None if atr else signal.get('target')
                risk_params = self.risk_manager.calculate_risk_parameters(
                    symbol=symbol,
                    signal_type=signal['signal'],
                    entry_price=current_price,
                    capital=account_info['available_capital'],
                    stop_loss=stop_in,
                    target=target_in,
                    atr=atr,
                )
                signal.update({
                    'position_size': risk_params.position_size,
                    'stop_loss': risk_params.stop_loss,
                    'target': risk_params.target,
                    'entry_price': risk_params.entry_price,
                    'risk_amount': risk_params.risk_amount,
                })

            signal['symbol'] = symbol
            return self.executor.execute_trade(signal, current_price)

        except Exception as e:
            logger.debug(f"Trade execution error for {symbol}: {e}")
            return {'status': 'ERROR', 'message': str(e)}
