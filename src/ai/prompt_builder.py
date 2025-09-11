"""AI prompt construction utilities."""

import json
import pandas as pd
from typing import Dict, Any
from src.config import (
    INITIAL_CAPITAL, MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT, 
    TAKE_PROFIT_PERCENT, RECENT_DATA_LOOKBACK
)


class PromptBuilder:
    """Build structured prompts for Claude AI."""
    
    @staticmethod
    def safe_format(value, default=0, decimals=2):
        """Safely format a value that might be None."""
        if value is None or pd.isna(value):
            value = default
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return f"{default:.{decimals}f}"
    
    @staticmethod
    def create_analysis_prompt(symbol: str, 
                             market_data: pd.DataFrame,
                             indicators: Dict[str, float],
                             context: Dict[str, Any] = None) -> str:
        """Create a structured analysis prompt for Claude."""
        
        if context is None:
            context = {}
        
        # Get recent price action
        recent_data = market_data.tail(RECENT_DATA_LOOKBACK)
        current = market_data.iloc[-1]
        
        # Calculate key metrics safely
        try:
            price_change_5d = ((current['close'] - market_data['close'].iloc[-5]) / 
                              market_data['close'].iloc[-5] * 100) if len(market_data) >= 5 else 0
        except (IndexError, KeyError, ZeroDivisionError):
            price_change_5d = 0
        
        try:
            high_20d = market_data['high'].tail(20).max() if len(market_data) >= 20 else current['high']
            low_20d = market_data['low'].tail(20).min() if len(market_data) >= 20 else current['low']
        except (KeyError, AttributeError):
            high_20d = current.get('high', current.get('close', 0))
            low_20d = current.get('low', current.get('close', 0))
        
        # Volume analysis
        current_volume = current.get('volume', 0)
        avg_volume = indicators.get('volume_avg_20', current_volume)
        try:
            volume_ratio = current_volume / avg_volume if avg_volume and avg_volume > 0 else 1.0
        except (TypeError, ZeroDivisionError):
            volume_ratio = 1.0
        
        # Safe current price
        try:
            current_price = float(current['close'])
        except (KeyError, TypeError, ValueError):
            current_price = 100.0  # Fallback price
        
        prompt = f"""You are an expert swing trading analyst for the Indian stock market (NSE). 
Analyze the following data for {symbol} and provide a trading recommendation.

CURRENT MARKET DATA:
- Symbol: {symbol}
- Current Price: ₹{current_price:.2f}
- Day Range: ₹{PromptBuilder.safe_format(current.get('low', current_price))} - ₹{PromptBuilder.safe_format(current.get('high', current_price))}
- Volume: {current_volume:,} (Ratio: {volume_ratio:.2f}x avg)
- 5-Day Change: {price_change_5d:.2f}%
- 20-Day Range: ₹{PromptBuilder.safe_format(low_20d, current_price)} - ₹{PromptBuilder.safe_format(high_20d, current_price)}

TECHNICAL INDICATORS:
- SMA 20: ₹{PromptBuilder.safe_format(indicators.get('sma_20'), current_price)}
- SMA 50: ₹{PromptBuilder.safe_format(indicators.get('sma_50'), current_price)}
- SMA 200: ₹{PromptBuilder.safe_format(indicators.get('sma_200'), current_price)}
- RSI (14): {PromptBuilder.safe_format(indicators.get('rsi_14'), 50, 1)}
- MACD: {PromptBuilder.safe_format(indicators.get('macd'), 0)}
- MACD Signal: {PromptBuilder.safe_format(indicators.get('macd_signal'), 0)}
- MACD Histogram: {PromptBuilder.safe_format(indicators.get('macd_histogram'), 0)}
- Price Change %: {PromptBuilder.safe_format(indicators.get('price_change_pct'), 0)}%

TRADING CONTEXT:
- Strategy: {context.get('strategy', 'Swing Trading (2-5 day holds)')}
- Capital: ₹{context.get('capital', INITIAL_CAPITAL)}
- Max Risk: {context.get('max_risk', MAX_RISK_PER_TRADE)*100:.1f}% per trade
- Risk Management: Stop loss at {context.get('stop_loss', STOP_LOSS_PERCENT)*100:.1f}%, Target at {context.get('take_profit', TAKE_PROFIT_PERCENT)*100:.1f}%

ANALYSIS CRITERIA:
1. Trend alignment (price vs moving averages)
2. Momentum indicators (RSI, MACD)
3. Volume confirmation
4. Risk-reward ratio
5. Clear support/resistance levels

CRITICAL: Respond ONLY with a valid JSON object in this exact format:
{{
    "signal": "BUY",
    "confidence": 0.75,
    "reasoning": "Brief explanation of your analysis",
    "entry_price": {current_price:.2f},
    "stop_loss": null,
    "target": null
}}

Valid signals: BUY, SELL, HOLD
Confidence: 0.0 to 1.0
For HOLD signals, set stop_loss and target to null.

Remember: We're swing trading with limited capital (₹{context.get('capital', INITIAL_CAPITAL)}), so capital preservation is crucial. Only suggest BUY/SELL with high confidence setups (confidence > 0.6). For lower confidence, use HOLD."""
        
        return prompt
    
    @staticmethod
    def parse_response(response_text: str, current_price: float = 100.0) -> Dict[str, Any]:
        """Parse Claude's response into structured data."""
        try:
            # Find JSON in response (Claude sometimes includes explanatory text)
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)
            
            # Extract and validate signal data
            signal = data.get('signal', 'HOLD').upper()
            confidence = float(data.get('confidence', 0.5))
            reasoning = data.get('reasoning', 'No reasoning provided')
            
            # Ensure signal is valid
            if signal not in ['BUY', 'SELL', 'HOLD']:
                signal = 'HOLD'
            
            # Ensure confidence is in valid range
            confidence = max(0.0, min(1.0, confidence))
            
            # Parse price-related fields
            entry_price = data.get('entry_price', current_price)
            stop_loss = data.get('stop_loss')
            target = data.get('target')
            
            return {
                'signal': signal,
                'confidence': confidence,
                'reasoning': reasoning,
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'target': target
            }
            
        except Exception as e:
            # Return safe default
            return {
                "signal": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Failed to parse response: {e}",
                "entry_price": current_price,
                "stop_loss": None,
                "target": None
            }
    
    @staticmethod
    def create_context(strategy: str = "swing", 
                      capital: float = INITIAL_CAPITAL,
                      risk_level: str = "moderate") -> Dict[str, Any]:
        """Create trading context for prompt."""
        risk_multipliers = {
            "conservative": 0.5,
            "moderate": 1.0,
            "aggressive": 1.5
        }
        
        multiplier = risk_multipliers.get(risk_level, 1.0)
        
        return {
            'strategy': f"{strategy.title()} Trading",
            'capital': capital,
            'max_risk': MAX_RISK_PER_TRADE * multiplier,
            'stop_loss': STOP_LOSS_PERCENT * multiplier,
            'take_profit': TAKE_PROFIT_PERCENT,
            'risk_level': risk_level
        }