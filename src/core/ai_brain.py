"""AI brain with enhanced error handling - supports Claude and Gemini providers.

TODO: MULTI-MODEL ARCHITECTURE IMPROVEMENTS
- Implement REST API fallback for Gemini (proven working via curl)
- Add OpenAI compatibility mode as alternative
- Consider hybrid approach: SDK first, REST fallback
- Add model-specific prompt optimization
- Implement cross-provider response validation
- Add provider health monitoring and auto-switching
"""

import time
from typing import Dict, Any, Optional, List
import pandas as pd
import anthropic
import requests
import json
from dataclasses import asdict

from src.interfaces import BaseDecisionModel, TradingSignal, MarketData
from src.ai.prompt_builder import PromptBuilder
from src.core.risk_manager import SimpleRiskManager
from src.data.config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE,
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_TOKENS, GEMINI_TEMPERATURE,
    AI_PROVIDER, INITIAL_CAPITAL, MAX_DECISION_HISTORY
)
from src.utils.logger import setup_logger
from src.utils.retry import retry_with_backoff
from src.exceptions import AIAnalysisError, ConfigurationError
from src.monitoring.performance import performance_tracker

logger = setup_logger(__name__, 'ai_brain.log')


class ClaudeAI(BaseDecisionModel):
    """Claude AI with robust error handling."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with error handling."""
        try:
            # Determine provider from config
            self.provider = AI_PROVIDER.lower()

            if self.provider == "claude":
                self._init_claude(api_key)
            elif self.provider == "gemini":
                self._init_gemini(api_key)
            else:
                raise ConfigurationError(f"Unknown AI provider: {self.provider}")

            self.prompt_builder = PromptBuilder()
            self.risk_manager = SimpleRiskManager()
            self.decision_history = []

            # Track API failures for circuit breaking
            self.consecutive_failures = 0
            self.max_consecutive_failures = 5

            logger.info(f"AI initialized - Provider: {self.provider}, Model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize AI: {e}")
            raise AIAnalysisError(f"AI initialization failed: {e}")

    def _init_claude(self, api_key: Optional[str] = None):
        """Initialize Claude provider."""
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY not configured")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = CLAUDE_MODEL
        self.max_tokens = CLAUDE_MAX_TOKENS
        self.temperature = CLAUDE_TEMPERATURE

    def _init_gemini(self, api_key: Optional[str] = None):
        """Initialize Gemini provider."""
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ConfigurationError("GEMINI_API_KEY not configured")

        # Use REST API instead of SDK (more reliable)
        self.client = "rest_api"  # Flag to use REST API
        self.model = GEMINI_MODEL
        self.max_tokens = GEMINI_MAX_TOKENS
        self.temperature = GEMINI_TEMPERATURE
    
    def get_required_indicators(self) -> list:
        """Return list of indicators this model needs."""
        return [
            "sma_20", "sma_50", "sma_200",
            "rsi_14",
            "macd", "macd_signal", "macd_histogram",
            "volume_avg_20",
            "price_change_pct"
        ]
    
    @performance_tracker("ai_analysis")
    def analyze(self, market_data: pd.DataFrame, 
               indicators: Dict[str, float]) -> Dict[str, Any]:
        """Analyze market with comprehensive error handling."""
        try:
            # Check if we've had too many failures
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.error(f"AI circuit breaker open - {self.consecutive_failures} consecutive failures")
                return self._safe_default_response("AI temporarily unavailable")
            
            # Debug: Check data format
            logger.debug(f"market_data type: {type(market_data)}")
            if isinstance(market_data, dict):
                logger.error(f"Received dict instead of DataFrame: {list(market_data.keys())}")
                return self._safe_default_response("Data format error - expected DataFrame")
            
            if not hasattr(market_data, 'iloc'):
                logger.error(f"Invalid market_data type: {type(market_data)}")
                return self._safe_default_response("Invalid data format")
            
            # Get symbol from DataFrame
            symbol = market_data['symbol'].iloc[-1] if 'symbol' in market_data else "UNKNOWN"
            current_price = float(market_data['close'].iloc[-1])
            
            # Create market data object for analysis
            latest_data = MarketData(
                symbol=symbol,
                timestamp=pd.Timestamp.now(),
                open=float(market_data['open'].iloc[-1]),
                high=float(market_data['high'].iloc[-1]),
                low=float(market_data['low'].iloc[-1]),
                close=current_price,
                volume=float(market_data['volume'].iloc[-1])
            )
            
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
                # TODO: Rule-based fallback disabled - for testing only
                # return self._fallback_analysis(latest_data, indicators)
                self.consecutive_failures += 1
                raise AIAnalysisError(f"AI analysis failed: {e}")

            # Parse response
            try:
                decision = self.prompt_builder.parse_response(
                    response_text, current_price
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse {self.provider.capitalize()} response: {e}")
                return self._safe_default_response("Parse error")
            
            # Validate decision
            if not self._validate_decision(decision):
                logger.warning(f"Invalid decision from {self.provider.capitalize()}")
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
    
    def _get_ai_response(self, prompt: str) -> str:
        """Get response from configured AI provider."""
        start_time = time.time()

        if self.provider == "claude":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
                timeout=30.0
            )
            response_text = response.content[0].text

        elif self.provider == "gemini":
            response_text = self._call_gemini_rest_api(prompt)

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        duration = time.time() - start_time
        logger.info(f"{self.provider.capitalize()} response received in {duration:.2f}s")
        logger.debug(f"Response: {response_text[:200]}...")  # Log first 200 chars

        return response_text

    def _get_portfolio_ai_response(self, prompt: str) -> str:
        """Get portfolio response from configured AI provider with longer timeout."""
        if self.provider == "claude":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens * 2,  # Increase tokens for portfolio
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
                timeout=60.0  # Longer timeout for portfolio analysis
            )
            return response.content[0].text

        elif self.provider == "gemini":
            return self._call_gemini_rest_api(prompt, max_tokens=self.max_tokens * 2)

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _call_gemini_rest_api(self, prompt: str, max_tokens: int = None) -> str:
        """Call Gemini using REST API (proven working method)."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_tokens or self.max_tokens,
                "candidateCount": 1
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        params = {
            "key": self.api_key
        }

        try:
            response = requests.post(url, json=payload, headers=headers, params=params, timeout=90)
            response.raise_for_status()

            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                if "content" in candidate:
                    content = candidate["content"]
                    # Handle both structures: with and without parts array
                    if "parts" in content and len(content["parts"]) > 0:
                        return content["parts"][0]["text"]
                    elif "text" in content:
                        return content["text"]
                    else:
                        # Fallback: try to find text anywhere in content
                        import json
                        logger.debug(f"Unexpected content structure: {json.dumps(content, indent=2)}")
                        raise Exception(f"No text found in content: {content}")
                else:
                    raise Exception(f"No content in candidate: {candidate}")
            else:
                raise Exception(f"No valid candidates in response: {result}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Gemini REST API error: {e}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini response: {e}")

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
        """Analyze portfolio with intelligent fallback to protect owned positions."""
        try:
            # Try efficient portfolio analysis first
            return self._analyze_portfolio_batch(portfolio_data, portfolio_indicators, context)
        except Exception as portfolio_error:
            logger.warning(f"Portfolio analysis failed: {portfolio_error}, using intelligent fallback")
            return self._intelligent_fallback_analysis(portfolio_data, portfolio_indicators, context, portfolio_error)

    def _analyze_portfolio_batch(self, portfolio_data: Dict[str, pd.DataFrame],
                                portfolio_indicators: Dict[str, Dict[str, float]],
                                context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze entire portfolio at once - scales from 1 to N symbols."""
        try:
            # Check circuit breaker
            if self.consecutive_failures >= self.max_consecutive_failures:
                logger.error(f"AI circuit breaker open - {self.consecutive_failures} consecutive failures")
                return self._safe_portfolio_default_response(list(portfolio_data.keys()), "AI temporarily unavailable")

            if context is None:
                context = {}

            # Build comprehensive portfolio prompt
            prompt = self.prompt_builder.create_portfolio_analysis_prompt(
                portfolio_data, portfolio_indicators, context
            )

            # Single AI API call for all symbols
            try:
                response_text = self._get_portfolio_ai_response(prompt)
            except Exception as e:
                pass  # Silent fallback for portfolio analysis
                self.consecutive_failures += 1
                return self._fallback_portfolio_analysis(portfolio_data, portfolio_indicators)

            # Parse portfolio response
            try:
                portfolio_decisions = self.prompt_builder.parse_portfolio_response(
                    response_text, portfolio_data, context
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse {self.provider.capitalize()} portfolio response: {e}")
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
                # TODO: Rule-based fallback disabled - for testing only
                # decisions[symbol] = self._fallback_analysis(market_data_obj, portfolio_indicators[symbol])
                raise Exception(f"Failed to analyze {symbol}")

        # This method should not be reached with fallbacks disabled
        raise Exception("Portfolio analysis failed - all AI methods exhausted")

    def _intelligent_fallback_analysis(self, portfolio_data: Dict[str, pd.DataFrame],
                                     portfolio_indicators: Dict[str, Dict[str, float]],
                                     context: Dict[str, Any], original_error: Exception) -> Dict[str, Any]:
        """Intelligent fallback: Individual analysis for owned positions, safe defaults for others."""
        if context is None:
            context = {}

        current_positions = context.get('current_positions', [])
        decisions = {}
        critical_symbols_analyzed = 0

        # Priority 1: Analyze owned positions individually to prevent losses
        if current_positions:
            logger.info(f"Portfolio analysis failed, analyzing {len(current_positions)} owned positions individually")

            for symbol in current_positions:
                if symbol in portfolio_data and symbol in portfolio_indicators:
                    try:
                        # Use existing single-symbol analysis for owned positions
                        market_data_obj = MarketData(
                            symbol=symbol,
                            timestamp=pd.Timestamp.now(),
                            open=float(portfolio_data[symbol]['open'].iloc[-1]),
                            high=float(portfolio_data[symbol]['high'].iloc[-1]),
                            low=float(portfolio_data[symbol]['low'].iloc[-1]),
                            close=float(portfolio_data[symbol]['close'].iloc[-1]),
                            volume=float(portfolio_data[symbol]['volume'].iloc[-1])
                        )

                        # Try AI analysis first, fallback to rule-based if needed
                        try:
                            decisions[symbol] = self.analyze(portfolio_data[symbol], portfolio_indicators[symbol])
                            critical_symbols_analyzed += 1
                            logger.debug(f"Individual AI analysis successful for owned position: {symbol}")
                        except Exception as individual_error:
                            logger.debug(f"AI analysis failed for {symbol}: {individual_error}")
                            # TODO: Rule-based fallback disabled - for testing only
                            # decisions[symbol] = self._fallback_analysis(market_data_obj, portfolio_indicators[symbol])
                            raise Exception(f"AI analysis failed for {symbol}: {individual_error}")

                    except Exception as symbol_error:
                        logger.error(f"Complete analysis failure for owned position {symbol}: {symbol_error}")
                        # Even owned positions get safe defaults if data is corrupted
                        decisions[symbol] = self._safe_default_response(f"Data error for owned position: {str(symbol_error)}")
                else:
                    logger.warning(f"Missing data for owned position {symbol}")
                    decisions[symbol] = self._safe_default_response(f"Missing data for owned position")

        # Priority 2: Safe defaults for non-owned symbols (no individual analysis needed)
        for symbol in portfolio_data.keys():
            if symbol not in decisions:
                decisions[symbol] = self._safe_default_response("Portfolio analysis failed - not owned, using safe default")

        fallback_type = "individual_analysis_for_owned" if current_positions else "safe_defaults_only"

        return {
            'market_analysis': f'Intelligent fallback due to portfolio error: {str(original_error)[:100]}. Protected {len(current_positions)} owned positions with individual analysis.',
            'decisions': decisions,
            'symbols_analyzed': len(decisions),
            'fallback_type': fallback_type,
            'critical_symbols_analyzed': critical_symbols_analyzed,
            'owned_positions_protected': len(current_positions)
        }
    
