"""Rule-based fallback decisions — used when all AI providers are unavailable.

A tiny RSI heuristic so the pipeline still produces a (low-confidence) signal
instead of a blind HOLD when every provider is rate-limited or down. It lives
apart from the AI engine so the "no AI" path is explicit and independently
testable, and so the engine reads as pure orchestration.
"""

from typing import Dict, Any

import pandas as pd

from src.platform.types import MarketData


def rule_based_decision(market_data: MarketData, indicators: Dict[str, float]) -> Dict[str, Any]:
    """Single-symbol RSI heuristic: oversold→BUY, overbought→SELL, else HOLD."""
    signal, confidence, reasoning = 'HOLD', 0.3, "Fallback rule-based analysis"

    rsi = indicators.get('rsi_14', 50)
    if rsi < 30:
        signal, confidence, reasoning = 'BUY', 0.4, f"Oversold condition (RSI={rsi:.1f})"
    elif rsi > 70:
        signal, confidence, reasoning = 'SELL', 0.4, f"Overbought condition (RSI={rsi:.1f})"

    return {
        'signal': signal,
        'confidence': confidence,
        'reasoning': reasoning,
        'entry_price': market_data.close,
        'stop_loss': None,
        'target': None,
        'position_size': None,
        'risk_amount': None,
    }


def rule_based_portfolio(portfolio_data: Dict[str, pd.DataFrame],
                         portfolio_indicators: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """Per-symbol rule-based decisions, wrapped in the ``{'decisions': ...}`` shape
    every caller expects (not a bare ``{symbol: decision}`` map)."""
    decisions = {}
    for symbol, data in portfolio_data.items():
        if symbol in portfolio_indicators:
            md = MarketData(
                symbol=symbol,
                timestamp=pd.Timestamp.now(),
                open=float(data['open'].iloc[-1]),
                high=float(data['high'].iloc[-1]),
                low=float(data['low'].iloc[-1]),
                close=float(data['close'].iloc[-1]),
                volume=float(data['volume'].iloc[-1]),
            )
            decisions[symbol] = rule_based_decision(md, portfolio_indicators[symbol])

    return {
        'market_analysis': 'Rule-based fallback (all AI providers unavailable)',
        'decisions': decisions,
        'symbols_analyzed': len(decisions),
    }
