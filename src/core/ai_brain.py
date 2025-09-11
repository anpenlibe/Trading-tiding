"""AI brain with enhanced error handling."""

import time
from typing import Dict, Any, Optional
import pandas as pd
import anthropic
import json
from dataclasses import asdict

from src.interfaces import BaseDecisionModel, TradingSignal, MarketData
from src.ai.prompt_builder import PromptBuilder
from src.core.risk_manager import SimpleRiskManager
from src.data.config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE,
    INITIAL_CAPITAL, MAX_DECISION_HISTORY
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
            self.api_key = api_key or ANTHROPIC_API_KEY
            if not self.api_key:
                raise ConfigurationError("ANTHROPIC_API_KEY not configured")
            
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = CLAUDE_MODEL
            self.prompt_builder = PromptBuilder()
            self.risk_manager = SimpleRiskManager()
            self.decision_history = []
            
            # Track API failures for circuit breaking
            self.consecutive_failures = 0
            self.max_consecutive_failures = 5
            
            logger.info(f"Claude AI initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Claude AI: {e}")
            raise AIAnalysisError(f"AI initialization failed: {e}")
    
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
            
            # Get Claude's response with timeout
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=CLAUDE_MAX_TOKENS,
                    temperature=CLAUDE_TEMPERATURE,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=30.0  # 30 second timeout
                )
            except anthropic.APITimeoutError:
                logger.warning("Claude API timeout - using fallback")
                self.consecutive_failures += 1
                return self._fallback_analysis(latest_data, indicators)
            except anthropic.APIError as e:
                logger.error(f"Claude API error: {e}")
                self.consecutive_failures += 1
                raise
            
            # Parse response
            try:
                decision = self.prompt_builder.parse_response(
                    response.content[0].text, current_price
                )
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Claude response: {e}")
                return self._safe_default_response("Parse error")
            
            # Validate decision
            if not self._validate_decision(decision):
                logger.warning("Invalid decision from Claude")
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
    
    @retry_with_backoff(max_retries=2, exceptions=(anthropic.APIError,))
    def _get_claude_response(self, prompt: str) -> str:
        """Get response from Claude API with retry logic."""
        try:
            start_time = time.time()
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                timeout=30.0
            )
            
            response = message.content[0].text
            duration = time.time() - start_time
            
            logger.info(f"Claude response received in {duration:.2f}s")
            logger.debug(f"Response: {response[:200]}...")  # Log first 200 chars
            
            return response
            
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise
    
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
    
