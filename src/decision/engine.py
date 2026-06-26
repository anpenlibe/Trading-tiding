"""AI brain with multi-provider fallback support.

Refactored architecture:
- Uses ProviderCoordinator for API calls with automatic fallback
- Default chain: Groq (gpt-oss-120b → llama-3.3-70b → gpt-oss-20b) → Gemini Pro
  → rule-based
- Maintains backward compatibility with existing applications
"""

import os
import time
from typing import Dict, Any, Optional, List
import pandas as pd

from src.platform.types import BaseDecisionModel
from src.decision.prompts import PromptBuilder
from src.decision.providers import ProviderCoordinator, build_portfolio_chain, build_symbol_chain
from src.decision.fallback import rule_based_portfolio
from src.platform.config import MAX_DECISION_HISTORY
from src.platform.logger import setup_logger, LOGS_DIR
from src.platform.errors import AIAnalysisError
from src.platform.events import log_event
from src.monitoring.performance import performance_tracker

logger = setup_logger(__name__, 'ai_brain.log')


class AIBrain(BaseDecisionModel):
    """AI decision model with multi-provider fallback support.

    Two prompt-specific chains (each key-cycled, mode-aware):
    - portfolio (long, all-symbols): Gemini Flash → llama-3.3-70b
    - single-symbol (short, special pass): gpt-oss-120b → llama-3.3-70b → gpt-oss-20b → Flash
    """

    def __init__(self, api_key: Optional[str] = None, temperature: float = 0.6,
                 mode: str = "backtest"):
        """Initialize with two provider coordinators (portfolio + single-symbol).

        Args:
            api_key: Deprecated (kept for backward compatibility, now ignored)
            temperature: Sampling temperature for all providers
            mode: 'backtest' (cycle keys 2..N) or 'live' (key 1 only)
        """
        try:
            self.mode = mode
            # The long all-symbols prompt and the short single-symbol prompt use
            # different model chains; each cycles its key pool (providers.build_*_chain).
            self.portfolio_coordinator = ProviderCoordinator(
                fallback_chain=build_portfolio_chain(mode), temperature=temperature)
            self.symbol_coordinator = ProviderCoordinator(
                fallback_chain=build_symbol_chain(mode), temperature=temperature)

            self.prompt_builder = PromptBuilder()
            self.decision_history = []

            # Model + pass type of the most recent AI call, stamped onto the
            # decision events emitted from the shared _log_decision funnel.
            self._last_model = None
            self._last_pass = None

            # Track API failures for this brain instance (coordinators have their own circuit breakers)
            self.consecutive_failures = 0
            self.max_consecutive_failures = 5

            logger.info(
                f"AI initialized (mode={mode}): portfolio chain "
                f"{len(self.portfolio_coordinator.fallback_chain)}, symbol chain "
                f"{len(self.symbol_coordinator.fallback_chain)}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize AI: {e}")
            raise AIAnalysisError(f"AI initialization failed: {e}")


    def _validate_decision(self, decision: Dict[str, Any]) -> bool:
        """Validate AI decision structure."""
        required_fields = ['signal', 'confidence', 'reasoning']
        
        # Check required fields
        for field in required_fields:
            if field not in decision:
                return False
        
        # Validate signal — full action vocabulary (BUY/SELL/HOLD + TRIM/ADD/MOVE_STOP).
        if decision['signal'] not in ('BUY', 'SELL', 'HOLD', 'TRIM', 'ADD', 'MOVE_STOP'):
            return False
        
        # Validate confidence
        if not isinstance(decision['confidence'], (int, float)):
            return False
        if not 0 <= decision['confidence'] <= 1:
            return False
        
        return True
    
    def _safe_default_response(self, reason: str) -> Dict[str, Any]:
        """Return safe default response."""
        return {
            'signal': 'HOLD',
            'confidence': 0.0,
            'reasoning': f'Safety mode: {reason}',
            'entry_price': None,
            'stop_loss': None,
            'target': None,
            'position_size': None,
            'risk_amount': None
        }
    
    def _get_ai_response(self, prompt: str, max_tokens: Optional[int] = None,
                         pass_type: str = 'special') -> str:
        """Get AI response via the fast single-symbol coordinator (short prompts).

        Used by the special pass and the consolidated alert review; ``pass_type`` stamps
        the telemetry so the two are distinguishable in the event stream.
        """
        start_time = time.time()

        response_text = self.symbol_coordinator.call_with_fallback(prompt, max_tokens=max_tokens)

        duration = time.time() - start_time
        provider = self.symbol_coordinator.get_current_provider() or "rule-based"
        logger.info(f"AI response from {provider} in {duration:.2f}s")
        logger.debug(f"Response: {response_text[:200]}...")  # Log first 200 chars

        self._last_model, self._last_pass = provider, pass_type
        log_event('ai_call', model=provider, latency=round(duration, 2), pass_type=pass_type)
        return response_text

    def _get_portfolio_ai_response(self, prompt: str) -> str:
        """Get portfolio AI response using coordinator.

        Note: max_tokens is handled by provider configs in coordinator.
        Groq uses 3000 (TPM limit), others use higher values.
        """
        start_time = time.time()
        response_text = self.portfolio_coordinator.call_with_fallback(prompt)
        duration = time.time() - start_time
        provider = self.portfolio_coordinator.get_current_provider() or "rule-based"
        logger.info(f"AI response from {provider} in {duration:.2f}s")

        self._last_model, self._last_pass = provider, 'general'
        log_event('ai_call', model=provider, latency=round(duration, 2), pass_type='general')
        return response_text


    def _log_decision(self, symbol: str, decision: Dict[str, Any],
                     market_data: pd.DataFrame, indicators: Dict[str, float]):
        """Log trading decision for analysis."""
        try:
            decision_record = {
                'timestamp': pd.Timestamp.now(),
                'symbol': symbol,
                'signal': decision['signal'],
                'confidence': decision['confidence'],
                'reasoning': decision['reasoning'][:100],  # Truncate for storage
                'price': float(market_data['close'].iloc[-1]),
                'rsi': indicators.get('rsi_14', 0),
                'macd': indicators.get('macd', 0)
            }
            
            self.decision_history.append(decision_record)
            
            # Keep history limited
            if len(self.decision_history) > MAX_DECISION_HISTORY:
                self.decision_history = self.decision_history[-MAX_DECISION_HISTORY:]
            
            logger.info(f"Decision logged: {symbol} - {decision['signal']} (confidence: {decision['confidence']:.2f})")

            log_event('decision', symbol=symbol, signal=decision['signal'],
                      confidence=round(float(decision['confidence']), 3),
                      model=self._last_model, pass_type=self._last_pass,
                      price=float(market_data['close'].iloc[-1]),
                      # Surface reasoning + thesis_status so rule-following (did the model
                      # act on its trigger? evolve its thesis?) is measurable from the
                      # event stream, not just buried in text logs.
                      reasoning=str(decision.get('reasoning', ''))[:240],
                      thesis_status=decision.get('thesis_status'))

        except Exception as e:
            logger.warning(f"Failed to log decision: {e}")
    
    def get_decision_history(self) -> list:
        """Get recent decision history."""
        return self.decision_history.copy()

    def recent_decisions_by_symbol(self, n: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """Last ``n`` decisions per symbol (most-recent-first) — the continuity trail
        threaded into the prompt so the model sees its own recent calls on a name and
        doesn't thrash (re-buy what it just sold, re-rate flat what it's been holding).
        Compact by design: only signal/confidence/reasoning, capped at n per symbol."""
        trail: Dict[str, List[Dict[str, Any]]] = {}
        for rec in reversed(self.decision_history):
            sym = rec.get('symbol')
            if not sym:
                continue
            bucket = trail.setdefault(sym, [])
            if len(bucket) < n:
                bucket.append({
                    'signal': rec.get('signal'),
                    'confidence': rec.get('confidence'),
                    'reasoning': str(rec.get('reasoning', ''))[:120],
                    'timestamp': str(rec.get('timestamp', '')),
                })
        return trail
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get AI performance statistics."""
        if not self.decision_history:
            return {}
        
        signals = [d['signal'] for d in self.decision_history]
        confidences = [d['confidence'] for d in self.decision_history]
        
        return {
            'total_decisions': len(self.decision_history),
            'buy_signals': signals.count('BUY'),
            'sell_signals': signals.count('SELL'),
            'hold_signals': signals.count('HOLD'),
            'avg_confidence': sum(confidences) / len(confidences),
            'high_confidence_decisions': sum(1 for c in confidences if c > 0.7),
            'last_decision_time': self.decision_history[-1]['timestamp'] if self.decision_history else None
        }
    
    def reset_history(self):
        """Reset decision history."""
        self.decision_history.clear()
        logger.info("Decision history reset")

    @performance_tracker("portfolio_analysis")
    def analyze_portfolio_with_intelligent_fallback(self, portfolio_data: Dict[str, pd.DataFrame],
                                                   portfolio_indicators: Dict[str, Dict[str, float]],
                                                   context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze portfolio with automatic multi-provider fallback.

        Coordinator handles fallback: Groq gpt-oss-120b → llama-3.3-70b → gpt-oss-20b → Gemini Pro → rule-based
        """
        return self._analyze_portfolio_batch(portfolio_data, portfolio_indicators, context)

    def _analyze_portfolio_batch(self, portfolio_data: Dict[str, pd.DataFrame],
                                portfolio_indicators: Dict[str, Dict[str, float]],
                                context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze entire portfolio at once - scales from 1 to N symbols."""
        try:
            if context is None:
                context = {}

            # Circuit breaker: once too many consecutive provider failures trip
            # it, skip the doomed API call — but STILL run the rule-based portfolio
            # fallback (RSI-based, no API calls) rather than returning blind HOLDs.
            # This is the path backtest uses, so a provider outage mid-run would
            # otherwise flatten every remaining timepoint to HOLD 0.0.
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.warning(
                    f"AI circuit breaker open ({self.consecutive_failures} failures) - using rule-based portfolio fallback"
                )
                return rule_based_portfolio(portfolio_data, portfolio_indicators)

            # Build comprehensive portfolio prompt
            prompt = self.prompt_builder.create_portfolio_analysis_prompt(
                portfolio_data, portfolio_indicators, context
            )

            # Single AI API call for all symbols (coordinator handles fallback)
            try:
                response_text = self._get_portfolio_ai_response(prompt)
            except Exception as e:
                # Coordinator handles all fallback internally, if we get here all providers failed
                logger.error(f"All AI providers failed for portfolio analysis: {type(e).__name__}: {e}")
                self.consecutive_failures += 1
                return rule_based_portfolio(portfolio_data, portfolio_indicators)

            # Parse portfolio response
            try:
                portfolio_decisions = self.prompt_builder.parse_portfolio_response(
                    response_text, portfolio_data, context
                )
                # Invalid SELLs (for unowned symbols) are prevented by the prompt and
                # enforced in TradingPipeline.run_decisions (has_position) — no extra
                # validation pass needed here.
            except ValueError as e:
                # parse_portfolio_response raises ValueError on unparseable output
                # (JSONDecodeError is a ValueError subclass). Catching ValueError —
                # not JSONDecodeError — is what makes this debug dump REACHABLE.
                provider = self.portfolio_coordinator.get_current_provider() or "AI"
                logger.warning(f"Failed to parse {provider} portfolio response: {e}")
                logger.error(f"Response text (first 500 chars): {response_text[:500]}")
                logger.error(f"Response text (last 300 chars): {response_text[-300:]}")
                # Save the malformed response to the canonical logs dir for debugging.
                try:
                    dump = os.path.join(LOGS_DIR, 'ai_malformed_response.txt')
                    with open(dump, 'w') as f:
                        f.write(response_text)
                    logger.error(f"Saved malformed response to {dump}")
                except Exception:
                    pass
                return self._safe_portfolio_default_response(list(portfolio_data.keys()), "Parse error")

            # Validate all decisions
            validated_decisions = {}
            for symbol, decision in portfolio_decisions.get('decisions', {}).items():
                if self._validate_decision(decision):
                    validated_decisions[symbol] = decision
                    # Log individual decisions (portfolio analysis doesn't have individual market data for logging)
                    try:
                        if symbol in portfolio_data:
                            symbol_indicators = portfolio_indicators.get(symbol, {})
                            self._log_decision(symbol, decision, portfolio_data[symbol], symbol_indicators)
                    except Exception as log_error:
                        logger.debug(f"Could not log decision for {symbol}: {log_error}")
                else:
                    # Fallback for invalid individual decision
                    validated_decisions[symbol] = self._safe_default_response(f"Invalid decision for {symbol}")

            # Reset failure counter on success
            self.consecutive_failures = 0

            # Note: Portfolio analysis completed (stats tracking handled by caller)

            return {
                'market_analysis': portfolio_decisions.get('market_analysis', ''),
                'decisions': validated_decisions,
                'timestamp': context.get('timestamp'),
                'symbols_analyzed': len(validated_decisions)
            }

        except Exception as e:
            error_msg = str(e)
            # Re-raise rate limit errors to trigger provider fallback
            if "429" in error_msg or "Too Many Requests" in error_msg or "rate limit" in error_msg.lower():
                raise  # Let the fallback handler deal with it

            logger.error(f"Portfolio analysis error: {e}")
            self.consecutive_failures += 1
            return self._safe_portfolio_default_response(list(portfolio_data.keys()), f"Analysis error: {str(e)}")

    @performance_tracker("alert_review")
    def analyze_alert_review(self, portfolio_data: Dict[str, pd.DataFrame],
                             portfolio_indicators: Dict[str, Dict[str, float]],
                             owned_symbols, candidate_symbols,
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Consolidated mid-cycle review over open positions ∪ surfaced candidates — ONE
        short prompt on the fast symbol chain → per-symbol decisions (same contract the
        portfolio parser reads). Degrades to the rule-based fallback like the other passes."""
        context = context or {}
        if self.consecutive_failures >= self.max_consecutive_failures:
            logger.warning("AI circuit breaker open - rule-based fallback for alert review")
            return rule_based_portfolio(portfolio_data, portfolio_indicators)

        prompt = self.prompt_builder.create_alert_review_prompt(
            portfolio_data, portfolio_indicators, owned_symbols, candidate_symbols, context
        )
        try:
            response_text = self._get_ai_response(prompt, pass_type='alert_review')
        except Exception as e:
            logger.warning(f"Alert-review AI call failed, rule-based fallback: {e}")
            self.consecutive_failures += 1
            return rule_based_portfolio(portfolio_data, portfolio_indicators)

        try:
            parsed = self.prompt_builder.parse_portfolio_response(response_text, portfolio_data, context)
        except ValueError as e:
            provider = self.symbol_coordinator.get_current_provider() or "AI"
            logger.warning(f"Failed to parse {provider} alert-review response: {e}")
            return self._safe_portfolio_default_response(list(portfolio_data.keys()), "Parse error")

        validated = {}
        for symbol, decision in parsed.get('decisions', {}).items():
            if self._validate_decision(decision):
                validated[symbol] = decision
                try:
                    self._log_decision(symbol, decision, portfolio_data[symbol],
                                       portfolio_indicators.get(symbol, {}))
                except Exception as log_error:
                    logger.debug(f"Could not log alert-review decision for {symbol}: {log_error}")
            else:
                validated[symbol] = self._safe_default_response(f"Invalid decision for {symbol}")

        self.consecutive_failures = 0
        return {'market_analysis': parsed.get('market_analysis', ''), 'decisions': validated}

    def _safe_portfolio_default_response(self, symbols: List[str], reason: str) -> Dict[str, Any]:
        """Safe default response for portfolio analysis."""
        decisions = {}
        for symbol in symbols:
            decisions[symbol] = self._safe_default_response(reason)

        return {
            'market_analysis': f'Default analysis due to: {reason}',
            'decisions': decisions,
            'symbols_analyzed': len(symbols)
        }

