"""AI prompt construction utilities."""

import json
import pandas as pd
from typing import Dict, Any
from src.platform.config import (
    INITIAL_CAPITAL, MAX_RISK_PER_TRADE,
    EMERGENCY_STOP_LOSS_PCT, EMERGENCY_TAKE_PROFIT_PCT, EMERGENCY_RECHECK_PCT,
    MIN_ACT_CONFIDENCE,
)
from src.features.indicators import summarize_market_regime
from src.platform.registry import get_stock_registry

# The action contract: the full verb vocabulary the pipeline/executor honor. SELL is a
# full close; TRIM/ADD/MOVE_STOP act on a held position. Anything else parses to HOLD.
VALID_SIGNALS = {'BUY', 'SELL', 'HOLD', 'TRIM', 'ADD', 'MOVE_STOP'}


def _coerce_float(value, default=None):
    """Float or default — keeps one malformed numeric field from sinking a whole decision."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
    def na(value, decimals=1):
        """Render a missing indicator as 'n/a' rather than a fabricated neutral default.

        safe_format substitutes a midpoint (RSI 50, SMA=price, vs-SMA 0%) for None, which
        a decision prompt reads as 'genuinely neutral' — indistinguishable from 'not warmed
        up yet'. For values where that confusion would mislead the model (trend/SMA during
        SMA-200 warmup), show 'n/a' so the model knows the signal is absent, not neutral."""
        if value is None or (hasattr(value, '__len__') and not isinstance(value, str)):
            return "n/a"
        try:
            if pd.isna(value):
                return "n/a"
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return "n/a"

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

        # Categorize stocks by ownership and watchlist. previous_watchlist now actually
        # flows from the prior pass (runners thread context['watchlist']); watchlist_thesis
        # carries WHY each was flagged, decision_trail the recent calls per symbol.
        owned_stocks = [s for s in symbols_list if s in current_positions]
        previous_watchlist = context.get('watchlist', [])
        watchlist_thesis = context.get('watchlist_thesis', {})
        decision_trail = context.get('decision_trail', {})
        watchlist_stocks = [s for s in symbols_list if s in previous_watchlist and s not in current_positions]

        floor = MIN_ACT_CONFIDENCE

        prompt = f"""You are an expert portfolio swing trader for NSE (Indian) equities, holding 2-5 days.
Analyze these {num_symbols} stocks together and return a decision for EACH — reasoning first, so the call follows from it.

ACCOUNT:
- Available capital ₹{available_capital:.2f} | max risk {context.get('max_risk', MAX_RISK_PER_TRADE)*100:.1f}% per trade | {context.get('timestamp', 'Current')}
- Market regime: {_regime_line(portfolio_indicators)}

ACTION RULES (enforced in code — violations are dropped, so don't waste them):
- [OWNED] you hold it → MANAGE it: HOLD, SELL (exit), TRIM (cut part, set trim_fraction), ADD (scale in), or MOVE_STOP (lock gains, set new_stop). Update its thesis_status (intact/weakening/invalidated). A profitable position with an INTACT thesis → MOVE_STOP/TRIM/HOLD, NEVER a reflexive SELL; SELL is for an INVALIDATED thesis. Always return revised emergency_thresholds.
- [WATCH] / [NEW] you don't hold it → BUY or HOLD only.
- CONFIDENCE both GATES and SIZES: below {floor:.2f} we do nothing (HOLD); at/above it a higher number takes a bigger position. {floor:.2f}=starter, 0.75=solid, 0.9+=high. Don't inflate it.
- You own the watchlist: flag a stock worth tracking with "watchlist": true + a one-line watchlist_reason + alert_conditions; drop ones that no longer interest you.
- Between full reviews, the system watches OWNED + WATCH every few minutes and wakes you on a single stock the moment one of its alert_conditions levels is crossed — so set those levels where you'd actually want to act.

OWNED ({len(owned_stocks)}): {', '.join(owned_stocks) if owned_stocks else 'none'}
WATCHLIST ({len(watchlist_stocks)}): {', '.join(watchlist_stocks) if watchlist_stocks else 'none'}

STOCKS (positive vs-SMA% = above = uptrend; RSI >70 overbought / <30 oversold; n/a = not warmed up):
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
                    allowed_actions = "HOLD/SELL/TRIM/ADD/MOVE_STOP"
                elif is_watchlist:
                    category = "[WATCH]"
                    allowed_actions = "BUY/HOLD"
                else:
                    category = "[NEW]"
                    allowed_actions = "BUY/HOLD"

                sf = PromptBuilder.safe_format
                na = PromptBuilder.na
                ind = indicators
                macd_state = "above-signal" if ind.get('macd_above_signal') else "below-signal"
                cross = ind.get('macd_cross')
                cross_lbl = "bull-cross" if cross == 1 else ("bear-cross" if cross == -1 else "no-cross")
                sector = sector_map.get(symbol, "")

                # Memory lines: a held position carries its thesis (manage against it); a
                # watch candidate carries WHY it was flagged; both carry the recent trail.
                mem_line = ""
                if is_owned and symbol in positions:
                    p = positions[symbol]
                    held = _held_days(p.get('entry_time'), context.get('timestamp'))
                    mem_line += (f"\n• Position: avg ₹{sf(p.get('entry_price'))}, "
                                 f"P&L {sf(p.get('pnl_percent'), 0, 1)}%"
                                 + (f", held {held}d" if held is not None else ""))
                    et = p.get('entry_thesis')
                    if et:
                        mem_line += f"\n• Your thesis ({p.get('thesis_status') or 'intact'}): {str(et)[:160]}"
                elif is_watchlist:
                    intent = (watchlist_thesis.get(symbol) or {}).get('reason')
                    if intent:
                        mem_line += f"\n• You're watching this because: {str(intent)[:160]}"
                trail = decision_trail.get(symbol)
                if trail:
                    recent = "; ".join(f"{t.get('signal')}@{t.get('confidence')}" for t in trail[:3])
                    mem_line += f"\n• Recent calls: {recent}"

                prompt += f"""
--- {symbol} {category}{f' [{sector}]' if sector else ''} ---
• Price ₹{current_price:.2f} | Allowed: {allowed_actions}{mem_line}
• Trend: vs SMA20 {na(ind.get('price_vs_sma20_pct'))}% / vs SMA50 {na(ind.get('price_vs_sma50_pct'))}% | 5-Day {price_change_5d:.2f}%
• Momentum: RSI {sf(ind.get('rsi_14'), 50, 1)} (Δ3 {sf(ind.get('rsi_trajectory'), 0, 1)}) | MACD {macd_state}/{cross_lbl} | Stoch%K {sf(ind.get('stoch_k'), 50, 0)} | ROC10 {sf(ind.get('roc_10'), 0, 1)}%
• Volatility: ATR {sf(ind.get('atr_14'))} | Boll%B {sf(ind.get('bollinger_pct_b'), 0, 2)} (BW {sf(ind.get('bollinger_bandwidth'), 0, 1)}%) | Range-pos {sf(ind.get('range_position'), 0, 2)}
• Volume: {volume_ratio:.2f}x avg | OBV-trend {sf(ind.get('obv_trend'), 0, 2)} | vol-trend {sf(ind.get('volume_trend'), 1, 2)}
"""

        prompt += f"""
HOW TO DECIDE (per stock) — reasoning first, then the call:
- Weigh trend + momentum + volume together; favor confluence over any single indicator. Keep portfolio diversification and the market regime above in mind.
- For OWNED stocks, judge them against the thesis shown above: is it intact, weakening, or invalidated? Then HOLD / ADD / TRIM / MOVE_STOP / SELL accordingly. For WATCH/NEW, BUY or HOLD.
- Confidence GATES and SIZES (see ACTION RULES): only BUY/ADD at/above {floor:.2f}; a higher number means a bigger position.
- alert_conditions = absolute levels to be woken on (price_above / price_below / rsi_below / volume_spike). Set them for OWNED and WATCH stocks.
- emergency_thresholds = percentages for OWNED stocks: stop_loss_pct (negative, e.g. {EMERGENCY_STOP_LOSS_PCT}), take_profit_pct (positive, e.g. {EMERGENCY_TAKE_PROFIT_PCT}), recheck_trigger_pct (move either way, e.g. {EMERGENCY_RECHECK_PCT}).
- Leave stop_loss and target null — the system applies ATR-based levels.

Respond with ONLY this JSON object (one entry per symbol), no other text:
{{
    "market_analysis": "2-3 sentences: regime, portfolio posture, any cross-stock theme",
    "decisions": {{"""

        # One worked example, applied to every symbol. The first symbol is a real one
        # from THIS universe (so the model sees the exact key shape); the WATCH example
        # uses a placeholder, never a real ticker, so it can't contaminate a real call.
        first_symbol = symbols_list[0]
        remaining_symbols = symbols_list[1:] if len(symbols_list) > 1 else []

        prompt += f"""
        "{first_symbol}": {{
            "reasoning": "1-2 sentences for {first_symbol} — what the indicators say",
            "signal": "BUY | SELL | HOLD | TRIM | ADD | MOVE_STOP",
            "confidence": 0.0-1.0,
            "thesis": "OWNED only: your updated one-line view (else null)",
            "thesis_status": "OWNED only: intact | weakening | invalidated (else null)",
            "trim_fraction": null,
            "new_stop": null,
            "watchlist": false,
            "watchlist_reason": null,
            "alert_conditions": null,
            "entry_price": null,
            "stop_loss": null,
            "target": null,
            "emergency_thresholds": {{"stop_loss_pct": {EMERGENCY_STOP_LOSS_PCT}, "take_profit_pct": {EMERGENCY_TAKE_PROFIT_PCT}, "recheck_trigger_pct": {EMERGENCY_RECHECK_PCT}}}
        }}"""

        if remaining_symbols:
            prompt += f""",
        ... same shape for every other symbol: {', '.join(remaining_symbols)}

        Example of a [WATCH] entry (placeholder key — flag it + set the levels that would make you act):
        "<A_WATCH_SYMBOL>": {{
            "reasoning": "Constructive but no entry yet",
            "signal": "HOLD",
            "confidence": 0.6,
            "thesis": null,
            "thesis_status": null,
            "trim_fraction": null,
            "new_stop": null,
            "watchlist": true,
            "watchlist_reason": "Want a pullback to support or oversold RSI",
            "alert_conditions": {{"price_below": 3150, "rsi_below": 30, "volume_spike": 2.0}},
            "entry_price": null,
            "stop_loss": null,
            "target": null,
            "emergency_thresholds": null
        }}"""

        prompt += """
    }
}

Set entry_price to the current price for BUY/ADD, null otherwise; stop_loss and target stay null (ATR handles them). TRIM needs trim_fraction (0..1); MOVE_STOP needs new_stop (below price, tighter than the current stop). OWNED stocks must include emergency_thresholds and a thesis_status; WATCH stocks must set watchlist:true plus alert_conditions."""

        return prompt

    @staticmethod
    def create_alert_review_prompt(portfolio_data: Dict[str, pd.DataFrame],
                                   portfolio_indicators: Dict[str, Dict[str, float]],
                                   owned_symbols, candidate_symbols,
                                   context: Dict[str, Any] = None) -> str:
        """Consolidated MID-CYCLE review (one prompt, replaces per-symbol special passes):
        recheck open positions (manage against thesis) + consider surfaced candidates
        (skeptically). Two framed sections, reasoning-first; same per-symbol action
        contract the portfolio parser reads."""
        if context is None:
            context = {}
        sf = PromptBuilder.safe_format
        na = PromptBuilder.na
        positions = context.get('positions', {})
        alert_ctx = context.get('alert_context', {})
        available_capital = context.get('account_info', {}).get('available_capital', INITIAL_CAPITAL)
        floor = MIN_ACT_CONFIDENCE

        def block(symbol: str, tag: str, allowed: str, extra: str) -> str:
            ind = portfolio_indicators.get(symbol, {})
            try:
                price = float(portfolio_data[symbol]['close'].iloc[-1])
            except Exception:
                price = 0.0
            macd_state = "above-signal" if ind.get('macd_above_signal') else "below-signal"
            return (f"\n--- {symbol} {tag} ---\n"
                    f"• Price ₹{price:.2f} | Allowed: {allowed}{extra}\n"
                    f"• Trend: vs SMA20 {na(ind.get('price_vs_sma20_pct'))}% / vs SMA50 {na(ind.get('price_vs_sma50_pct'))}%\n"
                    f"• Momentum: RSI {sf(ind.get('rsi_14'), 50, 1)} | MACD {macd_state} | Stoch%K {sf(ind.get('stoch_k'), 50, 0)}\n"
                    f"• Volatility: ATR {sf(ind.get('atr_14'))} | Boll%B {sf(ind.get('bollinger_pct_b'), 0, 2)}\n")

        prompt = f"""You are a disciplined swing trader for NSE (Indian) equities, holding 2-5 days.
This is a MID-CYCLE review between full portfolio reviews. Two jobs, reasoning first:
  1. RECHECK each open position — has anything unexpected happened that needs adjusting?
  2. CONSIDER the flagged candidates — skeptically.

ACCOUNT:
- Available capital ₹{available_capital:.2f} | {context.get('timestamp', 'Current')}
- Market regime: {_regime_line(portfolio_indicators)}
"""

        if owned_symbols:
            prompt += "\nYOUR OPEN POSITIONS — recheck + manage each against its thesis:\n"
            for s in owned_symbols:
                p = positions.get(s, {})
                pos_line = (f"\n• Holding: qty {p.get('quantity')} @ avg ₹{sf(p.get('entry_price'))} | "
                            f"P&L {sf(p.get('pnl_percent'), 0, 1)}% | stop ₹{sf(p.get('stop_loss'))} target ₹{sf(p.get('target'))}")
                et = p.get('entry_thesis')
                if et:
                    pos_line += f"\n• Your thesis ({p.get('thesis_status') or 'intact'}): {str(et)[:160]}"
                prompt += block(s, "[OWNED]", "HOLD/SELL/TRIM/ADD/MOVE_STOP", pos_line)
            prompt += ("\nMANAGING RULE: a profitable position with an INTACT thesis → MOVE_STOP (lock gains), "
                       "TRIM, or HOLD — NEVER a reflexive SELL. SELL only when the thesis is INVALIDATED.\n")

        if candidate_symbols:
            prompt += "\nFLAGGED FOR CONSIDERATION (a pullback signal tripped — MIGHT be interesting, not a buy order):\n"
            for s in candidate_symbols:
                fired = alert_ctx.get(s) or []
                conds = ", ".join(str(a.get('condition', '')).replace('_', ' ') for a in fired if a.get('condition'))
                why = f"\n• Why flagged: {conds}" if conds else ""
                prompt += block(s, "[WATCH]", "BUY/HOLD", why)
            prompt += ("\nCONSIDERATION RULE: a single signal is NOT a reason to buy. Default HOLD unless there is real "
                       "confluence (trend + momentum + volume) AND the regime supports new longs.\n")

        prompt += f"""
Confidence GATES and SIZES: only BUY/ADD at/above {floor:.2f}; a higher number takes a bigger position. Leave stop_loss/target null (ATR sets them).

Respond with ONLY this JSON object (one entry per symbol above), reasoning first:
{{
    "market_analysis": "1-2 sentences: what changed since the last full review",
    "decisions": {{
        "<SYMBOL>": {{
            "reasoning": "what the data says; for a holding, is the thesis intact/weakening/invalidated",
            "signal": "OWNED: HOLD|SELL|TRIM|ADD|MOVE_STOP  /  CANDIDATE: BUY|HOLD",
            "confidence": 0.0-1.0,
            "thesis": "owned only: updated one-line view (else null)",
            "thesis_status": "owned only: intact|weakening|invalidated (else null)",
            "trim_fraction": null,
            "new_stop": null,
            "entry_price": null, "stop_loss": null, "target": null,
            "emergency_thresholds": null
        }}
        ... one entry for EVERY symbol listed above
    }}
}}
Rules: SELL/TRIM/ADD/MOVE_STOP only on OWNED; BUY only on a candidate. TRIM needs trim_fraction (0..1); MOVE_STOP needs new_stop (below current price, tighter than the current stop). entry_price = current price for BUY/ADD, else null."""
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

                    # Validate and clean decision — full verb vocabulary now allowed.
                    signal = str(decision_data.get('signal', 'HOLD')).upper()
                    if signal not in VALID_SIGNALS:
                        signal = 'HOLD'

                    confidence = max(0.0, min(1.0, _coerce_float(decision_data.get('confidence'), 0.5)))

                    reasoning = decision_data.get('reasoning', f'Analysis for {symbol}')
                    entry_price = decision_data.get('entry_price', current_price if signal != 'HOLD' else None)
                    stop_loss = decision_data.get('stop_loss')
                    target = decision_data.get('target')
                    # Evolving thesis (OWNED) + verb parameters (TRIM / MOVE_STOP).
                    thesis = decision_data.get('thesis')
                    thesis_status = decision_data.get('thesis_status')
                    trim_fraction = _coerce_float(decision_data.get('trim_fraction'))
                    new_stop = _coerce_float(decision_data.get('new_stop'))

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
                        'thesis': thesis,
                        'thesis_status': thesis_status,
                        'trim_fraction': trim_fraction,
                        'new_stop': new_stop,
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
                        'thesis': None,
                        'thesis_status': None,
                        'trim_fraction': None,
                        'new_stop': None,
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