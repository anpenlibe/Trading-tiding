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

                trade_result = self._execute(symbol, decision, current_prices[symbol])
                if trade_result.get('status') == 'EXECUTED':
                    executed.append({
                        'symbol': symbol, 'decision': decision,
                        'price': current_prices[symbol], 'result': trade_result,
                    })

        return {'decisions': decisions, 'market_analysis': market_analysis, 'executed': executed}

    def _execute(self, symbol: str, signal: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Risk-validate + size + execute one signal at ``current_price``."""
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
                    signal, self.executor.get_positions()
                )
                if not is_valid:
                    return {'status': 'REJECTED', 'reason': rejection_reason}

                risk_params = self.risk_manager.calculate_risk_parameters(
                    symbol=symbol,
                    signal_type=signal['signal'],
                    entry_price=current_price,
                    capital=account_info['available_capital'],
                    stop_loss=signal.get('stop_loss'),
                    target=signal.get('target'),
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
