"""AI brain with multi-provider fallback support.

Refactored architecture:
- Uses ProviderCoordinator for API calls with automatic fallback
- Default chain: Groq (gpt-oss-120b → llama-3.3-70b → gpt-oss-20b) → Gemini Pro
  → Claude → rule-based
- Maintains backward compatibility with existing applications
"""

import time
from typing import Dict, Any, Optional, List
import pandas as pd
import json

from src.interfaces import BaseDecisionModel, MarketData
from src.ai.prompt_builder import PromptBuilder
from src.ai.provider_coordinator import ProviderCoordinator
from src.core.risk_manager import SimpleRiskManager
from src.data.config import INITIAL_CAPITAL, MAX_DECISION_HISTORY
from src.utils.logger import setup_logger
from src.exceptions import AIAnalysisError
from src.monitoring.performance import performance_tracker

logger = setup_logger(__name__, 'ai_brain.log')


class AIBrain(BaseDecisionModel):
    """AI decision model with multi-provider fallback support.

    Uses ProviderCoordinator internally for automatic fallback:
    Groq gpt-oss-120b → llama-3.3-70b → gpt-oss-20b → Gemini Pro → Claude → rule-based
    """

    def __init__(self, api_key: Optional[str] = None, temperature: float = 0.6):
        """Initialize with provider coordinator.

        Args:
            api_key: Deprecated (kept for backward compatibility, now ignored)
            temperature: Sampling temperature for all providers
        """
        try:
            # Initialize provider coordinator with fallback chain
            self.coordinator = ProviderCoordinator(temperature=temperature)

            self.prompt_builder = PromptBuilder()
            self.risk_manager = SimpleRiskManager()
            self.decision_history = []

            # Track API failures for this brain instance (coordinator has its own circuit breakers)
            self.consecutive_failures = 0
            self.max_consecutive_failures = 5

            logger.info(f"AI initialized with {len(self.coordinator.fallback_chain)} providers in fallback chain")
            logger.info(f"Current provider: {self.coordinator.get_current_provider()}")
        except Exception as e:
            logger.error(f"Failed to initialize AI: {e}")
            raise AIAnalysisError(f"AI initialization failed: {e}")


    @performance_tracker("ai_analysis")
    def analyze(self, market_data: pd.DataFrame, 
               indicators: Dict[str, float]) -> Dict[str, Any]:
        """Analyze market with comprehensive error handling."""
        try:
            # Validate data format first — without a usable DataFrame even the
            # rule-based fallback can't run, so a safe HOLD is the only option.
            if isinstance(market_data, dict):
                logger.error(f"Received dict instead of DataFrame: {list(market_data.keys())}")
                return self._safe_default_response("Data format error - expected DataFrame")

            if not hasattr(market_data, 'iloc'):
                logger.error(f"Invalid market_data type: {type(market_data)}")
                return self._safe_default_response("Invalid data format")

            # Extract the latest bar once — both the AI path and the rule-based
            # fallback below need it.
            symbol = market_data['symbol'].iloc[-1] if 'symbol' in market_data else "UNKNOWN"
            current_price = float(market_data['close'].iloc[-1])
            latest_data = MarketData(
                symbol=symbol,
                timestamp=pd.Timestamp.now(),
                open=float(market_data['open'].iloc[-1]),
                high=float(market_data['high'].iloc[-1]),
                low=float(market_data['low'].iloc[-1]),
                close=current_price,
                volume=float(market_data['volume'].iloc[-1])
            )

            # Circuit breaker: after too many consecutive provider failures, skip
            # the (doomed) API round-trip — but STILL run the rule-based fallback,
            # which makes no API calls. This used to return a blind HOLD, which
            # silently disabled the RSI fallback for the rest of a degraded run
            # (every remaining symbol got HOLD 0.0 instead of a real signal).
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.warning(
                    f"AI circuit breaker open ({self.consecutive_failures} failures) - using rule-based fallback"
                )
                return self._fallback_analysis(latest_data, indicators)

            # Build context
            context = {
                'strategy': 'swing',
                'risk_level': 'moderate',
                'market_hours': True
            }
            
            # Create prompt
            prompt = self.prompt_builder.create_analysis_prompt(
                symbol, market_data, indicators, context
            )
            
            # Get AI response
            try:
                response_text = self._get_ai_response(prompt)
            except Exception as e:
                # AI provider failed for this call: degrade gracefully to the
                # rule-based fallback, but still record the failure so the
                # circuit breaker (max_consecutive_failures) can escalate.
                self.consecutive_failures += 1
                logger.warning(f"AI response failed, using rule-based fallback: {e}")
                return self._fallback_analysis(latest_data, indicators)

            # Parse response
            try:
                decision = self.prompt_builder.parse_response(
                    response_text, current_price
                )
            except json.JSONDecodeError as e:
                provider = self.coordinator.get_current_provider() or "AI"
                logger.warning(f"Failed to parse {provider} response: {e}")
                return self._safe_default_response("Parse error")

            # Validate decision
            if not self._validate_decision(decision):
                provider = self.coordinator.get_current_provider() or "AI"
                logger.warning(f"Invalid decision from {provider}")
                return self._safe_default_response("Invalid decision")
            
            # Add risk parameters
            if decision['signal'] in ['BUY', 'SELL']:
                try:
                    risk_params = self.risk_manager.calculate_risk_parameters(
                        symbol=symbol,
                        signal_type=decision['signal'],
                        entry_price=current_price,
                        capital=INITIAL_CAPITAL
                    )
                    decision.update({
                        'position_size': risk_params.position_size,
                        'stop_loss': risk_params.stop_loss,
                        'target': risk_params.target,
                        'risk_amount': risk_params.risk_amount
                    })
                except Exception as e:
                    logger.warning(f"Failed to calculate risk parameters: {e}")
                    # Continue without risk parameters
            
            # Reset failure counter on success
            self.consecutive_failures = 0
            
            # Log decision
            self._log_decision(symbol, decision, market_data, indicators)
            
            logger.info(f"AI Decision: {decision['signal']} ({decision['confidence']:.1%})")
            return decision
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            self.consecutive_failures += 1
            return self._safe_default_response(f"Analysis error: {e}")
    
    def _validate_decision(self, decision: Dict[str, Any]) -> bool:
        """Validate AI decision structure."""
        required_fields = ['signal', 'confidence', 'reasoning']
        
        # Check required fields
        for field in required_fields:
            if field not in decision:
                return False
        
        # Validate signal
        if decision['signal'] not in ['BUY', 'SELL', 'HOLD']:
            return False
        
        # Validate confidence
        if not isinstance(decision['confidence'], (int, float)):
            return False
        if not 0 <= decision['confidence'] <= 1:
            return False
        
        return True
    
    def _validate_portfolio_positions(self, portfolio_decisions: Dict[str, Any],
                                      current_positions: List[str]) -> Dict[str, Any]:
        """Validate portfolio decisions against position constraints.

        Detects invalid SELL signals for stocks not owned.

        Args:
            portfolio_decisions: Parsed AI decisions for all symbols
            current_positions: List of symbols currently owned

        Returns:
            Portfolio decisions (with optional blocking if uncommented)
        """
        validated = portfolio_decisions.copy()
        decisions = validated.get('decisions', {})

        for symbol, decision in decisions.items():
            if decision.get('signal') == 'SELL' and symbol not in current_positions:
                logger.warning(f"🚫 AI Position Bug: Detected invalid SELL for unowned {symbol}")
                logger.debug(f"   Original reasoning: {decision.get('reasoning', 'N/A')}")

                # COMMENTED OUT: Uncomment to block invalid SELLs
                # decision['signal'] = 'HOLD'
                # decision['confidence'] = 0.0
                # decision['reasoning'] = f"[BLOCKED: Cannot SELL unowned stock] Original: {decision.get('reasoning', 'N/A')[:100]}"

        return validated

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
    
    def _fallback_analysis(self, market_data: MarketData, 
                          indicators: Dict[str, float]) -> Dict[str, Any]:
        """Simple rule-based fallback when AI is unavailable."""
        signal = 'HOLD'
        confidence = 0.3
        reasoning = "Fallback rule-based analysis"
        
        # Simple RSI-based rules
        rsi = indicators.get('rsi_14', 50)
        if rsi < 30:
            signal = 'BUY'
            confidence = 0.4
            reasoning = f"Oversold condition (RSI={rsi:.1f})"
        elif rsi > 70:
            signal = 'SELL'
            confidence = 0.4
            reasoning = f"Overbought condition (RSI={rsi:.1f})"
        
        return {
            'signal': signal,
            'confidence': confidence,
            'reasoning': reasoning,
            'entry_price': market_data.close,
            'stop_loss': None,
            'target': None,
            'position_size': None,
            'risk_amount': None
        }
    
    def _get_ai_response(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Get AI response using coordinator with automatic fallback.

        Args:
            prompt: The prompt to send
            max_tokens: Optional max_tokens override

        Returns:
            AI response text
        """
        start_time = time.time()

        response_text = self.coordinator.call_with_fallback(prompt, max_tokens=max_tokens)

        duration = time.time() - start_time
        provider = self.coordinator.get_current_provider() or "rule-based"
        logger.info(f"AI response from {provider} in {duration:.2f}s")
        logger.debug(f"Response: {response_text[:200]}...")  # Log first 200 chars

        return response_text

    def _get_portfolio_ai_response(self, prompt: str) -> str:
        """Get portfolio AI response using coordinator.

        Note: max_tokens is handled by provider configs in coordinator.
        Groq uses 3000 (TPM limit), others use higher values.
        """
        return self.coordinator.call_with_fallback(prompt)


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
            
        except Exception as e:
            logger.warning(f"Failed to log decision: {e}")
    
    def get_decision_history(self) -> list:
        """Get recent decision history."""
        return self.decision_history.copy()
    
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

        Coordinator handles fallback: Groq gpt-oss-120b → llama-3.3-70b → gpt-oss-20b → Gemini Pro → Claude → rule-based
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
                return self._fallback_portfolio_analysis(portfolio_data, portfolio_indicators)

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
                return self._fallback_portfolio_analysis(portfolio_data, portfolio_indicators)

            # Parse portfolio response
            try:
                portfolio_decisions = self.prompt_builder.parse_portfolio_response(
                    response_text, portfolio_data, context
                )

                # Validate position constraints (currently just logs, doesn't block)
                current_positions = context.get('current_positions', [])
                portfolio_decisions = self._validate_portfolio_positions(portfolio_decisions, current_positions)

            except json.JSONDecodeError as e:
                provider = self.coordinator.get_current_provider() or "AI"
                logger.warning(f"Failed to parse {provider} portfolio response: {e}")
                logger.error(f"Response text (first 500 chars): {response_text[:500]}")
                logger.error(f"Response text (last 300 chars): {response_text[-300:]}")
                # Save malformed response for debugging
                try:
                    with open('/tmp/ai_malformed_response.txt', 'w') as f:
                        f.write(response_text)
                    logger.error("Saved malformed response to /tmp/ai_malformed_response.txt")
                except:
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

    def _fallback_portfolio_analysis(self, portfolio_data: Dict[str, pd.DataFrame],
                                   portfolio_indicators: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Fallback portfolio analysis using simple rules."""
        decisions = {}

        for symbol, data in portfolio_data.items():
            if symbol in portfolio_indicators:
                # Use existing single-symbol fallback
                market_data_obj = MarketData(
                    symbol=symbol,
                    timestamp=pd.Timestamp.now(),
                    open=float(data['open'].iloc[-1]),
                    high=float(data['high'].iloc[-1]),
                    low=float(data['low'].iloc[-1]),
                    close=float(data['close'].iloc[-1]),
                    volume=float(data['volume'].iloc[-1])
                )
                decisions[symbol] = self._fallback_analysis(
                    market_data_obj, portfolio_indicators[symbol]
                )

        # Return the wrapped shape every caller expects ({'decisions': ...}),
        # not a bare {symbol: decision} map.
        return {
            'market_analysis': 'Rule-based fallback (all AI providers unavailable)',
            'decisions': decisions,
            'symbols_analyzed': len(decisions),
        }

