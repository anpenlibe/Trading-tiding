# Tests

Regression tests pinning correctness bugs fixed in the codebase. They are
deterministic and make **no network or AI-provider calls** (the AI fallback
tests stub the coordinator), so the suite runs in well under a second.

```bash
# from the repo root, with the venv active
python -m pytest            # run everything
python -m pytest tests/test_paper_trader.py -v
```

## Coverage

| File | Pins |
|------|------|
| `test_risk_manager.py` | SELL exits not blocked; BUY needs entry_price (no crash); position-size capital cap |
| `test_paper_trader.py` | buy/sell execution; stop-loss & target auto-close without crash; capital consistency after close; full-position close on partial sell |
| `test_config.py` | registry helpers reach real data (import-path fix); env-knob defaults |
| `test_ai_fallback.py` | coordinator raises on exhaustion; rule-based RSI fallback; wrapped `{'decisions': ...}` shape |

These are intentionally focused on pure/fast logic. Higher layers (live data,
real provider calls, full backtest runs) are exercised manually via
`apps/health_check.py` and the trading apps.
