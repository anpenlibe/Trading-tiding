"""AI prompt construction utilities."""

import json
import pandas as pd
from typing import Dict, Any
from src.data.config import (
    INITIAL_CAPITAL, MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT,
    TAKE_PROFIT_PERCENT, RECENT_DATA_LOOKBACK,
    EMERGENCY_STOP_LOSS_PCT, EMERGENCY_TAKE_PROFIT_PCT, EMERGENCY_RECHECK_PCT
)


class PromptBuilder:
    """Build structured prompts for Claude AI."""
    
    @staticmethod
    def safe_format(value, default=0, decimals=2):
        """Safely format a value that might be None."""
        if value is None:
            value = default
        elif hasattr(value, '__len__') and not isinstance(value, str):
            # Handle arrays, lists, etc.
            value = default
        elif pd.isna(value):
            value = default
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return f"{default:.{decimals}f}"

    @staticmethod
    def extract_emergency_thresholds(thresholds: dict, is_owned: bool, signal: str) -> dict:
        """Extract thresholds with consistent defaults."""
        # Apply thresholds if AI provided them, position is owned, or signal is active
        should_monitor = (
            any(thresholds.get(key) is not None for key in ['stop_loss_pct', 'take_profit_pct', 'recheck_trigger_pct']) or
            is_owned or
            signal in ['BUY', 'SELL']
        )

        if should_monitor:
            return {
                'stop_loss_pct': thresholds.get('stop_loss_pct') if thresholds.get('stop_loss_pct') is not None else EMERGENCY_STOP_LOSS_PCT,
                'take_profit_pct': thresholds.get('take_profit_pct') if thresholds.get('take_profit_pct') is not None else EMERGENCY_TAKE_PROFIT_PCT,
                'recheck_trigger_pct': thresholds.get('recheck_trigger_pct') if thresholds.get('recheck_trigger_pct') is not None else EMERGENCY_RECHECK_PCT,
                'comment': thresholds.get('comment') or 'Standard monitoring'
            }
        else:
            return {
                'stop_loss_pct': None,
                'take_profit_pct': None,
                'recheck_trigger_pct': None,
                'comment': None
            }
    
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

    @staticmethod
    def create_portfolio_analysis_prompt(portfolio_data: Dict[str, pd.DataFrame],
                                       portfolio_indicators: Dict[str, Dict[str, float]],
                                       context: Dict[str, Any] = None) -> str:
        """Create portfolio analysis prompt for multiple symbols at once."""

        if context is None:
            context = {}

        # Build market overview section
        symbols_list = list(portfolio_data.keys())
        num_symbols = len(symbols_list)

        current_positions = context.get('current_positions', [])
        account_info = context.get('account_info', {})
        available_capital = account_info.get('available_capital', INITIAL_CAPITAL)

        prompt = f"""You are an expert portfolio swing trader for the Indian stock market (NSE).
Analyze the following {num_symbols} stocks simultaneously and provide trading recommendations for each.

PORTFOLIO CONTEXT:
- Symbols: {', '.join(symbols_list)}
- Strategy: {context.get('strategy', 'Swing Trading (2-5 day holds)')}
- Available Capital: ₹{available_capital:.2f}
- Current Positions: {', '.join(current_positions) if current_positions else 'None'}
- Max Risk: {context.get('max_risk', MAX_RISK_PER_TRADE)*100:.1f}% per trade
- Timestamp: {context.get('timestamp', 'Current')}

IMPORTANT: Only suggest SELL signals for stocks you currently hold: {current_positions if current_positions else 'NONE'}

INDIVIDUAL STOCK ANALYSIS:
"""

        # Add each symbol's data
        for symbol in symbols_list:
            if symbol in portfolio_data and symbol in portfolio_indicators:
                stock_data = portfolio_data[symbol]
                indicators = portfolio_indicators[symbol]

                # Get current data safely
                try:
                    current = stock_data.iloc[-1]
                    current_price = float(current['close'])

                    # Calculate price changes
                    price_change_5d = 0
                    if len(stock_data) >= 5:
                        try:
                            price_change_5d = ((current_price - float(stock_data['close'].iloc[-5])) /
                                             float(stock_data['close'].iloc[-5]) * 100)
                        except (ZeroDivisionError, KeyError):
                            pass

                    # Volume analysis
                    current_volume = current.get('volume', 0)
                    avg_volume = indicators.get('volume_avg_20', current_volume)
                    volume_ratio = current_volume / avg_volume if avg_volume and avg_volume > 0 else 1.0

                except (IndexError, KeyError, ValueError):
                    current_price = 100.0
                    current_volume = 0
                    volume_ratio = 1.0
                    price_change_5d = 0

                prompt += f"""
--- {symbol} ---
• Current Price: ₹{current_price:.2f}
• 5-Day Change: {price_change_5d:.2f}%
• Volume Ratio: {volume_ratio:.2f}x
• Technical Indicators:
  - SMA 20: ₹{PromptBuilder.safe_format(indicators.get('sma_20'), current_price)}
  - SMA 50: ₹{PromptBuilder.safe_format(indicators.get('sma_50'), current_price)}
  - RSI (14): {PromptBuilder.safe_format(indicators.get('rsi_14'), 50, 1)}
  - MACD: {PromptBuilder.safe_format(indicators.get('macd'), 0)}
  - MACD Signal: {PromptBuilder.safe_format(indicators.get('macd_signal'), 0)}
"""

        prompt += f"""
ANALYSIS REQUIREMENTS:
1. Consider each stock individually for technical signals
2. Look for portfolio-wide patterns and correlations
3. Ensure proper diversification in recommendations
4. Apply consistent risk management across all positions
5. Only suggest BUY/SELL with high confidence (>0.6)

CRITICAL: Respond with a valid JSON object in this EXACT format:
{{
    "market_analysis": "Brief overall market view and portfolio insights",
    "decisions": {{"""

        # Add expected decision format for each symbol
        for i, symbol in enumerate(symbols_list):
            comma = "," if i < len(symbols_list) - 1 else ""
            prompt += f"""
        "{symbol}": {{
            "signal": "BUY/SELL/HOLD",
            "confidence": 0.75,
            "reasoning": "Brief analysis for {symbol}",
            "entry_price": null,
            "stop_loss": null,
            "take_profit": null,
            "emergency_thresholds": {{
                "stop_loss_pct": {EMERGENCY_STOP_LOSS_PCT},
                "take_profit_pct": {EMERGENCY_TAKE_PROFIT_PCT},
                "recheck_trigger_pct": {EMERGENCY_RECHECK_PCT}
            }}
        }}{comma}"""

        prompt += """
    }
}

Valid signals: BUY, SELL, HOLD
Confidence: 0.0 to 1.0
Set entry_price to current price for BUY/SELL, null for HOLD
Set stop_loss and take_profit to null for HOLD signals

EMERGENCY THRESHOLDS (provide for ALL positions):
- stop_loss_pct: Negative percentage to trigger emergency sell analysis (e.g., {EMERGENCY_STOP_LOSS_PCT} for {abs(EMERGENCY_STOP_LOSS_PCT):.1f}% loss)
- take_profit_pct: Positive percentage to trigger emergency profit-taking analysis (e.g., {EMERGENCY_TAKE_PROFIT_PCT} for {EMERGENCY_TAKE_PROFIT_PCT:.1f}% gain)
- recheck_trigger_pct: Percentage move in either direction to trigger position re-evaluation (e.g., {EMERGENCY_RECHECK_PCT})
"""

        return prompt

    @staticmethod
    def parse_portfolio_response(response_text: str,
                               portfolio_data: Dict[str, pd.DataFrame],
                               context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Parse Claude's portfolio response into structured data."""
        try:
            # Find JSON in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in portfolio response")

            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)

            # Extract market analysis
            market_analysis = data.get('market_analysis', 'No market analysis provided')

            # Process each symbol's decision
            decisions = {}
            raw_decisions = data.get('decisions', {})

            for symbol in portfolio_data.keys():
                if symbol in raw_decisions:
                    decision_data = raw_decisions[symbol]

                    # Handle null decision case to prevent crashes
                    if not isinstance(decision_data, dict):
                        decision_data = {}

                    # Get current price for this symbol
                    try:
                        current_price = float(portfolio_data[symbol]['close'].iloc[-1])
                    except (KeyError, IndexError, ValueError):
                        current_price = 100.0

                    # Validate and clean decision
                    signal = decision_data.get('signal', 'HOLD').upper()
                    if signal not in ['BUY', 'SELL', 'HOLD']:
                        signal = 'HOLD'

                    confidence = float(decision_data.get('confidence', 0.5))
                    confidence = max(0.0, min(1.0, confidence))

                    reasoning = decision_data.get('reasoning', f'Analysis for {symbol}')
                    entry_price = decision_data.get('entry_price', current_price if signal != 'HOLD' else None)
                    stop_loss = decision_data.get('stop_loss')
                    target = decision_data.get('target')

                    # Extract and process emergency thresholds using simplified logic
                    emergency_thresholds = decision_data.get('emergency_thresholds', {})
                    if not isinstance(emergency_thresholds, dict):
                        emergency_thresholds = {}

                    # Check if this is an owned position
                    current_positions = context.get('current_positions', []) if context else []
                    is_owned = symbol in current_positions

                    # Use simplified threshold extraction
                    processed_thresholds = PromptBuilder.extract_emergency_thresholds(
                        emergency_thresholds, is_owned, signal
                    )

                    decisions[symbol] = {
                        'signal': signal,
                        'confidence': confidence,
                        'reasoning': reasoning,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'target': target,
                        'emergency_thresholds': processed_thresholds
                    }
                else:
                    # Default decision if symbol missing from response
                    current_positions = context.get('current_positions', []) if context else []
                    is_owned = symbol in current_positions

                    # Use same simplified threshold logic for defaults
                    default_thresholds = PromptBuilder.extract_emergency_thresholds({}, is_owned, 'HOLD')

                    decisions[symbol] = {
                        'signal': 'HOLD',
                        'confidence': 0.3,
                        'reasoning': f'No analysis provided for {symbol}',
                        'entry_price': None,
                        'stop_loss': None,
                        'target': None,
                        'emergency_thresholds': default_thresholds
                    }

            return {
                'market_analysis': market_analysis,
                'decisions': decisions
            }

        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse portfolio response: {e}")