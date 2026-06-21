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
        
        # Why this special pass fired — the breached alert(s). Telling the model the
        # trigger turns a generic re-analysis into a reaction to a specific event.
        alert_section = ""
        alert_trigger = context.get('alert_trigger')
        if alert_trigger:
            lines = []
            for a in alert_trigger:
                # Prefer the specific condition (approaching_stop / macd_bullish_cross /
                # price_above …) over the coarse enum type — it tells the model exactly
                # what tripped, including whether it's managing its own stop/target.
                t = (a.get('condition') or a.get('type') or 'alert').replace('_', ' ')
                val = PromptBuilder.safe_format(a.get('value'))
                thr = a.get('threshold')
                lines.append(f"- {t}: current {val}" + (f" (threshold {PromptBuilder.safe_format(thr)})" if thr else ""))
            alert_section = (
                f"\nWHY YOU ARE ANALYZING {symbol} NOW (alert(s) fired since the last full review — "
                f"act on this trigger, don't just re-rate the stock):\n" + "\n".join(lines) + "\n")

        # Held-position context: if we own this symbol, tell the model our entry,
        # P&L and stop/target so it can MANAGE the position (trim/hold/exit) rather
        # than re-rate it as if flat. Mirrors the portfolio prompt's position line.
        position = context.get('position')
        if position and position.get('quantity'):
            pos_section = (
                f"\nYOUR CURRENT POSITION IN {symbol} (you own this — decide whether to HOLD, add, or SELL):\n"
                f"- Qty {position.get('quantity')} @ entry ₹{PromptBuilder.safe_format(position.get('entry_price'))}"
                f" | unrealized P&L {PromptBuilder.safe_format(position.get('pnl_percent'), 0, 1)}%"
                f" | stop ₹{PromptBuilder.safe_format(position.get('stop_loss'))}"
                f" target ₹{PromptBuilder.safe_format(position.get('target'))}\n")
        else:
            pos_section = f"\nYOU DO NOT HOLD {symbol} (a SELL is not possible — choose BUY or HOLD).\n"

        sf = PromptBuilder.safe_format
        ind = indicators
        macd_state = "above-signal" if ind.get('macd') is not None and ind.get('macd_signal') is not None and ind.get('macd') > ind.get('macd_signal') else "below-signal"
        capital = context.get('capital', INITIAL_CAPITAL)

        prompt = f"""You are a disciplined swing trader for NSE (Indian) equities, holding 2-5 days.
You are being asked about ONE stock, {symbol}, right now — for the specific reason below. \
Act on that reason; don't re-rate the stock from scratch.
{alert_section}{pos_section}
PRICE & VOLUME ({symbol}):
- Last ₹{current_price:.2f} | day ₹{sf(current.get('low', current_price))}–₹{sf(current.get('high', current_price))} | 20-day ₹{sf(low_20d, current_price)}–₹{sf(high_20d, current_price)}
- Volume {current_volume:,} ({volume_ratio:.2f}x 20d avg) | 5-day change {price_change_5d:.2f}%

TREND (where price sits vs its moving averages):
- SMA20 ₹{sf(ind.get('sma_20'), current_price)} / SMA50 ₹{sf(ind.get('sma_50'), current_price)} / SMA200 ₹{sf(ind.get('sma_200'), current_price)}
- Price vs SMA20/50: {sf(ind.get('price_vs_sma20_pct'), 0, 1)}% / {sf(ind.get('price_vs_sma50_pct'), 0, 1)}%  (positive = above = uptrend)

MOMENTUM:
- RSI14 {sf(ind.get('rsi_14'), 50, 1)} (Δ3 {sf(ind.get('rsi_trajectory'), 0, 1)}; >70 overbought, <30 oversold) | Stoch %K/%D {sf(ind.get('stoch_k'), 50, 0)}/{sf(ind.get('stoch_d'), 50, 0)} | ROC10 {sf(ind.get('roc_10'), 0, 1)}%
- MACD {sf(ind.get('macd'), 0)} / signal {sf(ind.get('macd_signal'), 0)} / hist {sf(ind.get('macd_histogram'), 0)} ({macd_state})

VOLATILITY & FLOW:
- ATR14 {sf(ind.get('atr_14'))} | Bollinger %B {sf(ind.get('bollinger_pct_b'), 0, 2)} (BW {sf(ind.get('bollinger_bandwidth'), 0, 1)}%; >1 above upper band, <0 below lower) | range-pos {sf(ind.get('range_position'), 0, 2)} | OBV-trend {sf(ind.get('obv_trend'), 0, 2)}

HOW TO DECIDE:
- Start from the reason you were woken (the trigger and your position, if any), then confirm or veto it with trend + momentum + volume. Favor confluence over any single indicator.
- Capital is limited (₹{capital}) — protect it. When the signal is mixed, HOLD.
- Calibrate confidence: 0.5 = coin-flip/unclear, 0.6–0.7 = decent confluence, 0.8+ = strong multi-signal setup. Only act (BUY/SELL) above 0.6; otherwise HOLD.
- You may leave stop_loss and target null — the system applies volatility-scaled (ATR) levels, so a templated ±% is not useful.

Respond with ONLY this JSON object, no other text:
{{
    "signal": "BUY | SELL | HOLD",
    "confidence": 0.0-1.0,
    "reasoning": "1-2 sentences naming the trigger and the indicators that decided it",
    "entry_price": null,
    "stop_loss": null,
    "target": null
}}

Rules: SELL is only valid if you hold {symbol}. For BUY/SELL set entry_price to the current price (₹{current_price:.2f}); for HOLD set entry_price, stop_loss and target all to null."""
        
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
            # Parse-or-raise: a parser must not fabricate a HOLD, which would hide
            # the failure and pollute decision history with a fake decision. Raise a
            # uniform ValueError (mirroring parse_portfolio_response) and let the
            # engine — the single owner of degradation policy — choose the fallback.
            raise ValueError(f"Failed to parse single-symbol response: {e}")
    
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

        prompt = f"""You are an expert portfolio swing trader for NSE (Indian) equities, holding 2-5 days.
Analyze these {num_symbols} stocks together and return a decision for EACH.

ACCOUNT:
- Available capital ₹{available_capital:.2f} | max risk {context.get('max_risk', MAX_RISK_PER_TRADE)*100:.1f}% per trade | {context.get('timestamp', 'Current')}
- Market regime: {_regime_line(portfolio_indicators)}

ACTION RULES (enforced in code — violations are dropped, so don't waste them):
- [OWNED] you hold it  → SELL or HOLD only; always return revised emergency_thresholds for it.
- [WATCH] / [NEW] you don't hold it → BUY or HOLD only.
- You own the watchlist: flag a stock worth tracking with "watchlist": true + alert_conditions; drop ones that no longer interest you. Give a one-line watchlist_reason.
- Between full reviews, the system watches OWNED + WATCH every few minutes and wakes you on a single stock the moment one of its alert_conditions levels is crossed — so set those levels where you'd actually want to act.

OWNED ({len(owned_stocks)}): {', '.join(owned_stocks) if owned_stocks else 'none'}
WATCHLIST ({len(watchlist_stocks)}): {', '.join(watchlist_stocks) if watchlist_stocks else 'none'}

STOCKS (positive vs-SMA% = above = uptrend; RSI >70 overbought / <30 oversold):
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
                    category = "[OWNED]"
                    allowed_actions = "SELL/HOLD"
                elif is_watchlist:
                    category = "[WATCH]"
                    allowed_actions = "BUY/HOLD"
                else:
                    category = "[NEW]"
                    allowed_actions = "BUY/HOLD"

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
HOW TO DECIDE (per stock):
- Weigh trend + momentum + volume together; favor confluence over any single indicator. Keep portfolio diversification and the market regime above in mind.
- Calibrate confidence: 0.5 = unclear, 0.6–0.7 = decent confluence, 0.8+ = strong setup. Only BUY/SELL above 0.6; otherwise HOLD.
- alert_conditions = absolute levels you want to be woken on (price_above / price_below / rsi_below / volume_spike). Set them for OWNED and WATCH stocks.
- emergency_thresholds = percentages for OWNED stocks: stop_loss_pct (negative, e.g. {EMERGENCY_STOP_LOSS_PCT}), take_profit_pct (positive, e.g. {EMERGENCY_TAKE_PROFIT_PCT}), recheck_trigger_pct (move either way, e.g. {EMERGENCY_RECHECK_PCT}).
- Leave stop_loss and target null — the system applies ATR-based levels.

Respond with ONLY this JSON object (one entry per symbol), no other text:
{{
    "market_analysis": "2-3 sentences: regime, portfolio posture, any cross-stock theme",
    "watchlist": ["symbols you want tracked"],
    "decisions": {{"""

        # Add expected decision format - show one example, apply to all symbols
        first_symbol = symbols_list[0]
        remaining_symbols = symbols_list[1:] if len(symbols_list) > 1 else []

        prompt += f"""
        "{first_symbol}": {{
            "signal": "BUY | SELL | HOLD",
            "confidence": 0.0-1.0,
            "reasoning": "1-2 sentences for {first_symbol}",
            "watchlist": false,
            "watchlist_reason": null,
            "entry_price": null,
            "stop_loss": null,
            "target": null,
            "emergency_thresholds": {{"stop_loss_pct": {EMERGENCY_STOP_LOSS_PCT}, "take_profit_pct": {EMERGENCY_TAKE_PROFIT_PCT}, "recheck_trigger_pct": {EMERGENCY_RECHECK_PCT}}},
            "alert_conditions": null
        }}"""

        if remaining_symbols:
            prompt += f""",
        ... same shape for every other symbol: {', '.join(remaining_symbols)}

        Example of a [WATCH] stock (flag it, set the levels that would make you act):
        "TCS": {{
            "signal": "HOLD",
            "confidence": 0.6,
            "reasoning": "Constructive but no entry yet",
            "watchlist": true,
            "watchlist_reason": "Want a pullback to ~3150 or oversold RSI",
            "entry_price": null,
            "stop_loss": null,
            "target": null,
            "emergency_thresholds": null,
            "alert_conditions": {{"price_below": 3150, "rsi_below": 30, "volume_spike": 2.0}}
        }}"""

        prompt += """
    }
}

Set entry_price to the current price for BUY/SELL, null for HOLD; stop_loss and target stay null (ATR handles them). OWNED stocks must include emergency_thresholds; WATCH stocks must set watchlist:true plus alert_conditions."""

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