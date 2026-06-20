"""AI prompt construction utilities."""

import json
import pandas as pd
from typing import Dict, Any
from src.platform.config import (
    INITIAL_CAPITAL, MAX_RISK_PER_TRADE, STOP_LOSS_PERCENT,
    TAKE_PROFIT_PERCENT, RECENT_DATA_LOOKBACK,
    EMERGENCY_STOP_LOSS_PCT, EMERGENCY_TAKE_PROFIT_PCT, EMERGENCY_RECHECK_PCT
)
from src.features.indicators import summarize_market_regime
from src.platform.registry import get_stock_registry


def _sector_map(symbols) -> Dict[str, str]:
    """{symbol: sector} via the stock registry; safe/empty on failure."""
    out: Dict[str, str] = {}
    try:
        reg = get_stock_registry()
        for s in symbols:
            info = reg.get_stock_info(s)
            if info and getattr(info, "sector", None):
                out[s] = info.sector.value
    except Exception:
        pass
    return out


def _held_days(entry_time, now) -> Any:
    """Whole days a position has been held (entry_time vs now), or None."""
    try:
        return max(0, (pd.Timestamp(now).normalize() - pd.Timestamp(entry_time).normalize()).days)
    except Exception:
        return None


def _regime_line(portfolio_indicators: Dict[str, Dict[str, float]]) -> str:
    """One-line market-regime summary (breadth-based, + index trend if present)."""
    r = summarize_market_regime(portfolio_indicators)
    if not r:
        return "n/a"
    line = (f"{str(r['regime']).upper()} — breadth {r.get('pct_above_sma50')}% of "
            f"{r.get('breadth_n')} stocks above SMA50, avg RSI {r.get('avg_rsi')}")
    if r.get("index_rsi") is not None:
        line += f"; Nifty RSI {r.get('index_rsi')}, vs SMA50 {r.get('index_vs_sma50_pct')}%"
    return line


class PromptBuilder:
    """Build structured prompts for the AI decision model (provider-agnostic).

    Produces the single-symbol and portfolio-batch prompts and parses the JSON
    responses back into decision dicts. Used for whichever provider the
    coordinator routes to (Groq/Gemini), provider-agnostic.
    """
    
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
        """Create a structured single-symbol analysis prompt for the AI."""
        
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
- ATR (14): {PromptBuilder.safe_format(indicators.get('atr_14'))} | Bollinger %B: {PromptBuilder.safe_format(indicators.get('bollinger_pct_b'), 0, 2)} (BW {PromptBuilder.safe_format(indicators.get('bollinger_bandwidth'), 0, 1)}%)
- RSI trajectory Δ3: {PromptBuilder.safe_format(indicators.get('rsi_trajectory'), 0, 1)} | Stoch %K/%D: {PromptBuilder.safe_format(indicators.get('stoch_k'), 50, 0)}/{PromptBuilder.safe_format(indicators.get('stoch_d'), 50, 0)} | ROC(10): {PromptBuilder.safe_format(indicators.get('roc_10'), 0, 1)}%
- Price vs SMA20/50: {PromptBuilder.safe_format(indicators.get('price_vs_sma20_pct'), 0, 1)}%/{PromptBuilder.safe_format(indicators.get('price_vs_sma50_pct'), 0, 1)}% | Range-pos: {PromptBuilder.safe_format(indicators.get('range_position'), 0, 2)} | OBV-trend: {PromptBuilder.safe_format(indicators.get('obv_trend'), 0, 2)}

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
    "stop_loss": {current_price * 0.985:.2f},
    "target": {current_price * 1.03:.2f}
}}

Valid signals: BUY, SELL, HOLD
Confidence: 0.0 to 1.0
For BUY: Set stop_loss below entry_price, target above entry_price (or null for system defaults)
For SELL: Set stop_loss above entry_price, target below entry_price (or null for system defaults)
For HOLD: Set stop_loss and target to null.

Remember: We're swing trading with limited capital (₹{context.get('capital', INITIAL_CAPITAL)}), so capital preservation is crucial. Only suggest BUY/SELL with high confidence setups (confidence > 0.6). For lower confidence, use HOLD."""
        
        return prompt
    
    @staticmethod
    def parse_response(response_text: str, current_price: float = 100.0) -> Dict[str, Any]:
        """Parse the AI's single-symbol JSON response into a decision dict."""
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
        positions = context.get('positions', {})
        sector_map = _sector_map(symbols_list)

        # Categorize stocks by ownership and watchlist
        owned_stocks = [s for s in symbols_list if s in current_positions]
        previous_watchlist = context.get('watchlist', [])
        watchlist_stocks = [s for s in symbols_list if s in previous_watchlist and s not in current_positions]
        remaining_stocks = [s for s in symbols_list if s not in current_positions and s not in previous_watchlist]

        prompt = f"""You are an expert portfolio swing trader for the Indian stock market (NSE).
Analyze the following {num_symbols} stocks simultaneously and provide trading recommendations for each.

PORTFOLIO CONTEXT:
- Symbols: {', '.join(symbols_list)}
- Strategy: {context.get('strategy', 'Swing Trading (2-5 day holds)')}
- Available Capital: ₹{available_capital:.2f}
- Max Risk: {context.get('max_risk', MAX_RISK_PER_TRADE)*100:.1f}% per trade
- Timestamp: {context.get('timestamp', 'Current')}
- MARKET REGIME: {_regime_line(portfolio_indicators)}

CRITICAL TRADING RULES - MUST FOLLOW:
═══════════════════════════════════════
🔵 OWNED POSITIONS ({len(owned_stocks)}): {', '.join(owned_stocks) if owned_stocks else 'NONE'}
   → Allowed Actions: SELL or HOLD only
   → You ALREADY hold these stocks
   → REVISE emergency thresholds each cycle based on current market conditions

🟣 WATCHLIST ({len(watchlist_stocks)}): {', '.join(watchlist_stocks) if watchlist_stocks else 'NONE'}
   → Stocks YOU flagged for close monitoring
   → Allowed Actions: BUY or HOLD only
   → YOU MAINTAIN THIS LIST - add/remove stocks as you see fit
   → Set custom alert thresholds for entry opportunities

🟡 REMAINING ({len(remaining_stocks)}): {', '.join(remaining_stocks[:8])}{'...' if len(remaining_stocks) > 8 else ''}
   → Allowed Actions: BUY or HOLD only
   → Add promising stocks to WATCHLIST for monitoring

⚠️  VIOLATION WARNING: Any SELL signal for unowned stocks (🟣/🟡) will be REJECTED
═══════════════════════════════════════

YOUR WATCHLIST RESPONSIBILITIES:
1. MAINTAIN: Add stocks showing potential, remove when no longer interesting
2. MONITOR: Set custom alert thresholds (price levels, RSI, volume, etc.)
3. EXPLAIN: Provide clear reason why each stock is on watchlist
4. REVISE: Update thresholds for owned positions each cycle
5. CONTEXT: Between scheduled cycles (90min), system monitors 🔵 OWNED + 🟣 WATCHLIST every 5 minutes
6. ALERTS: When threshold triggers, you'll get emergency analysis request for that stock + all owned positions

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

                # Visual categorization with watchlist
                is_owned = symbol in current_positions
                is_watchlist = symbol in watchlist_stocks

                if is_owned:
                    category = "🔵 OWNED"
                    allowed_actions = "SELL/HOLD only"
                elif is_watchlist:
                    category = "🟣 WATCHLIST"
                    allowed_actions = "BUY/HOLD only (on YOUR watchlist)"
                else:
                    category = "🟡 REMAINING"
                    allowed_actions = "BUY/HOLD only"

                sf = PromptBuilder.safe_format
                ind = indicators
                macd_state = "above-signal" if ind.get('macd_above_signal') else "below-signal"
                cross = ind.get('macd_cross')
                cross_lbl = "bull-cross" if cross == 1 else ("bear-cross" if cross == -1 else "no-cross")
                sector = sector_map.get(symbol, "")
                pos_line = ""
                if is_owned and symbol in positions:
                    p = positions[symbol]
                    held = _held_days(p.get('entry_time'), context.get('timestamp'))
                    pos_line = (f"\n• Position: entry ₹{sf(p.get('entry_price'))}, "
                                f"P&L {sf(p.get('pnl_percent'), 0, 1)}%"
                                + (f", held {held}d" if held is not None else ""))

                prompt += f"""
--- {symbol} {category}{f' [{sector}]' if sector else ''} ---
• Price ₹{current_price:.2f} | Allowed: {allowed_actions}{pos_line}
• Trend: vs SMA20 {sf(ind.get('price_vs_sma20_pct'), 0, 1)}% / vs SMA50 {sf(ind.get('price_vs_sma50_pct'), 0, 1)}% | 5-Day {price_change_5d:.2f}%
• Momentum: RSI {sf(ind.get('rsi_14'), 50, 1)} (Δ3 {sf(ind.get('rsi_trajectory'), 0, 1)}) | MACD {macd_state}/{cross_lbl} | Stoch%K {sf(ind.get('stoch_k'), 50, 0)} | ROC10 {sf(ind.get('roc_10'), 0, 1)}%
• Volatility: ATR {sf(ind.get('atr_14'))} | Boll%B {sf(ind.get('bollinger_pct_b'), 0, 2)} (BW {sf(ind.get('bollinger_bandwidth'), 0, 1)}%) | Range-pos {sf(ind.get('range_position'), 0, 2)}
• Volume: {volume_ratio:.2f}x avg | OBV-trend {sf(ind.get('obv_trend'), 0, 2)} | vol-trend {sf(ind.get('volume_trend'), 1, 2)}
"""

        prompt += f"""
ANALYSIS REQUIREMENTS:
1. Consider each stock individually for technical signals
2. Look for portfolio-wide patterns and correlations
3. Ensure proper diversification in recommendations
4. Apply consistent risk management across all positions
5. Only suggest BUY/SELL with high confidence (>0.6)
6. MAINTAIN YOUR WATCHLIST: Add promising stocks, remove when no longer interesting
7. For 🔵 OWNED: Always provide revised emergency_thresholds (percentage-based)
8. For 🟣 WATCHLIST: Set watchlist=true and provide alert_conditions (absolute values)

CRITICAL: Respond with a valid JSON object in this EXACT format:
{{
    "market_analysis": "Brief overall market view and portfolio insights",
    "watchlist": ["SYMBOL1", "SYMBOL2"],
    "decisions": {{"""

        # Add expected decision format - show one example, apply to all symbols
        first_symbol = symbols_list[0]
        remaining_symbols = symbols_list[1:] if len(symbols_list) > 1 else []

        prompt += f"""
        "{first_symbol}": {{
            "signal": "BUY/SELL/HOLD",
            "confidence": 0.75,
            "reasoning": "Brief analysis for {first_symbol}",
            "watchlist": false,
            "watchlist_reason": null,
            "entry_price": null,
            "stop_loss": null,
            "take_profit": null,
            "emergency_thresholds": {{
                "stop_loss_pct": {EMERGENCY_STOP_LOSS_PCT},
                "take_profit_pct": {EMERGENCY_TAKE_PROFIT_PCT},
                "recheck_trigger_pct": {EMERGENCY_RECHECK_PCT}
            }},
            "alert_conditions": null
        }}"""

        if remaining_symbols:
            prompt += f""",
        ... (apply same format for: {', '.join(remaining_symbols)})

        Example for 🟣 WATCHLIST stock:
        "TCS": {{
            "signal": "HOLD",
            "confidence": 0.65,
            "reasoning": "Strong fundamentals, waiting for entry",
            "watchlist": true,
            "watchlist_reason": "Wait for pullback to ₹3,150 or RSI oversold",
            "entry_price": null,
            "stop_loss": null,
            "take_profit": null,
            "emergency_thresholds": null,
            "alert_conditions": {{
                "price_below": 3150,
                "rsi_below": 30,
                "volume_spike": 2.0
            }}
        }}"""

        prompt += f"""
    }}
}}

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
        """Parse the AI's portfolio JSON response into per-symbol decision dicts."""
        try:
            # Find JSON in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in portfolio response")

            json_str = response_text[start_idx:end_idx]
            data = json.loads(json_str)

            # Extract market analysis and watchlist
            market_analysis = data.get('market_analysis', 'No market analysis provided')
            watchlist = data.get('watchlist', [])
            if not isinstance(watchlist, list):
                watchlist = []

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

                    # Extract watchlist information
                    watchlist_flag = decision_data.get('watchlist', False)
                    watchlist_reason = decision_data.get('watchlist_reason', None)
                    alert_conditions = decision_data.get('alert_conditions', None)
                    if not isinstance(alert_conditions, dict):
                        alert_conditions = None

                    decisions[symbol] = {
                        'signal': signal,
                        'confidence': confidence,
                        'reasoning': reasoning,
                        'watchlist': watchlist_flag,
                        'watchlist_reason': watchlist_reason,
                        'alert_conditions': alert_conditions,
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
                        'watchlist': False,
                        'watchlist_reason': None,
                        'alert_conditions': None,
                        'entry_price': None,
                        'stop_loss': None,
                        'target': None,
                        'emergency_thresholds': default_thresholds
                    }

            return {
                'market_analysis': market_analysis,
                'watchlist': watchlist,
                'decisions': decisions
            }

        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"Failed to parse portfolio response: {e}")