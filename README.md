# trading-tiding

**AI-assisted swing-trading research bot for the NSE (Indian equities).**

`trading-tiding` collects market data for a curated set of NSE stocks, computes
technical indicators, and asks a large language model to make paper-trading
decisions under explicit risk limits. It is an **educational / research project
and a paper-trading simulator — not investment advice.** See the
[disclaimer](#disclaimer) before doing anything with real money.

---

## Highlights

- **Multi-provider AI with automatic fallback** — Groq → Gemini → Claude, plus a
  rule-based fallback if every provider is unavailable. Per-provider circuit
  breakers and rate-limit handling are built in.
- **Risk-managed paper trading** — position sizing, per-trade risk caps, daily
  loss limits, and max-drawdown guards before any simulated order.
- **Event-driven alerts** — instead of polling on a fixed timer, the alert engine
  reacts to price moves, RSI extremes, volume spikes, and MACD crossovers.
- **Offline backtesting** — a bundled historical OHLCV snapshot lets the
  backtester run with no API keys at all.
- **Safety first** — paper trading is the default; mock data is blocked in live
  mode; live trading requires deliberate configuration.

---

## How it works

```
apps/  ──►  src/core  ──►  src/ai          (decisions)
  │           │      └──►  src/data         (market data, config, registry)
  │           └────────►   src/alerts       (event detection)
  └─ CLI entry points      src/utils        (logging, db tools)
```

1. **Data** — live OHLCV comes from Zerodha Kite Connect; backtests read the
   bundled historical SQLite snapshot (offline, no keys). If Zerodha is
   unavailable in paper mode, the collector falls back to a built-in **mock**
   generator (random bars, for pipeline testing only). *(A `YahooFinanceAPI` is
   implemented in `data_sources.py` but is not currently wired into the
   collector.)*
2. **Indicators** — RSI, MACD, and SMAs are computed per symbol.
3. **AI decision** — `src/ai/provider_coordinator.py` builds a market-context
   prompt and queries the first available provider in the fallback chain. Groq
   and Gemini are called over their REST APIs (via `requests`); Claude uses the
   `anthropic` SDK. Each decision carries a signal, a confidence score, and the
   model's reasoning.
4. **Risk + execution** — `SimpleRiskManager` sizes the position and enforces
   limits; `PaperTrader` simulates the fill with slippage and commission and
   tracks P&L.

## Requirements

- **Python 3.10+** (developed on 3.12; `pandas`/`numpy` pins require ≥3.9)
- At least **one** AI provider API key (Groq, Gemini, or Anthropic)
- *(Optional)* a Zerodha Kite Connect account for live NSE data — without it you
  can still run **backtests** against the bundled dataset (live/paper cycles fall
  back to mock data)

## Installation

```bash
git clone <repository-url>
cd trading-tiding

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit .env (see Configuration)
```

## Configuration

All configuration lives in `.env`. **`.env.example` is the canonical, fully
documented list** — copy it and fill in what you need. The only hard requirement
is one AI provider key:

```bash
# Set at least ONE of these:
GROQ_API_KEY=...        # console.groq.com   (fast, generous free tier)
GEMINI_API_KEY=...      # aistudio.google.com
ANTHROPIC_API_KEY=...   # console.anthropic.com
```

Everything else has sensible defaults. The knobs you are most likely to touch:

| Variable | Default | Purpose |
|---|---|---|
| `ENABLED_AI_PROVIDERS` | `groq,gemini,claude` | Providers (and order) for the fallback chain. A provider is used only if listed **and** its key is set. |
| `TRADING_STRATEGY` | `swing` | Symbol selection: `conservative`, `swing`, `diversified`, or `tech_focus`. |
| `INITIAL_CAPITAL` | `10000.0` | Starting paper-trading capital (₹). |
| `MAX_RISK_PER_TRADE` | `0.015` | Fraction of capital risked per trade (1.5%). |
| `DRY_RUN` / `TRADING_MODE` | `true` / `paper` | Safety toggles. Paper trading is the default. |
| `ZERODHA_API_KEY` *(+secret/token)* | — | Enable live NSE data. Without it, live cycles fall back to mock; backtests use the bundled dataset. |

> See `.env.example` for the full set (AI models, indicator periods, emergency
> thresholds, validation limits, etc.).

### Live NSE data (optional)

Zerodha access tokens expire daily. Generate one via the helper script, which
walks the OAuth flow and writes the token back to `.env`:

```bash
python scripts/generate_zerodha_token.py
```

Re-run it whenever you see "Unauthorized" / "Token expired".

## Usage

All apps are run from the repo root.

```bash
# System diagnostics
python apps/health_check.py            # full check
python apps/health_check.py --quick    # fast subset

# Run one AI-driven trading cycle (paper / test mode) and print a report
python apps/trader.py

# Backtest against historical data
python apps/backtest.py --auto                          # defaults (3 days)
python apps/backtest.py --days 30 --speed 10
python apps/backtest.py --start-date 2025-09-01 --end-date 2025-09-30
python apps/backtest.py --symbols TCS INFY HDFCBANK

# Collect / refresh market data
python apps/data_collector.py --period 6mo
python apps/data_collector.py --days 30 --symbols RELIANCE TCS

# Monitor performance
python apps/monitor.py                  # one-shot snapshot
python apps/monitor.py --continuous     # refresh every 30s
python apps/monitor.py --auto --export  # automated + export report
```

> **Note:** `apps/trader.py` currently runs a *single* trading cycle in
> paper/test mode and prints a performance report — it is a demonstration entry
> point, not a long-running daemon.

## Project structure

```
apps/            CLI entry points (trader, backtest, data_collector, monitor, health_check)
src/core/        AI brain, risk manager, paper trader, indicators, trading modes
src/data/        config, data sources, database, stock registry, validation, cache
src/ai/          provider coordinator, prompt builder, provider clients (claude/gemini/groq)
src/alerts/      event-driven alert engine and rules
src/monitoring/  performance tracking and dashboard
src/utils/       logging, database optimization
scripts/         operational helpers (e.g. Zerodha token generation)
docs/            user docs; docs/dev/ holds internal notes & research
data/            runtime data — logs, caches, DBs (gitignored)
```

## Supported stocks & strategies

The registry (`src/data/stock_registry.py`) covers **27 NSE stocks across 9
sectors** (Technology, Banking, Energy, FMCG, Pharma, Telecom, Metals, Auto,
Infrastructure), each tagged with market cap and liquidity. `TRADING_STRATEGY`
selects a subset:

- **conservative** — large-cap, high-liquidity names
- **swing** — medium-volatility swing candidates *(default)*
- **diversified** — spread across sectors
- **tech_focus** — technology + banking tilt

The Nifty 50 index (`^NSEI`) is always included for market-regime context.

## Safety features

- **Paper trading by default** — no real orders unless you deliberately enable
  live mode.
- **Mock-data lockout** — simulated data can never be used in live trading.
- **Real-data requirement for live trading** — live mode requires an
  authenticated data source.
- **Risk guards** — per-trade risk, daily loss, and max-drawdown limits, plus a
  >20% price-move circuit breaker on incoming data.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Please set at least one AI API key...` | Add `GROQ_API_KEY`, `GEMINI_API_KEY`, or `ANTHROPIC_API_KEY` to `.env`. |
| "Unauthorized" / "Token expired" | Re-run `python scripts/generate_zerodha_token.py` (Zerodha tokens expire daily). |
| No live data | Without a valid Zerodha token, live cycles fall back to mock data; use `apps/backtest.py` against the bundled dataset instead. |
| General health | Run `python apps/health_check.py` for a full diagnosis. |

Logs are written under `data/logs/`.

## Project status & limitations

- **Research / paper-trading focus.** Live-trading code paths exist but are gated
  and lightly exercised — treat live use as experimental and at your own risk.
- **No automated test suite ships yet.** `pytest` is listed as a dev dependency;
  contributions adding tests are welcome.
- **Bundled market data.** A historical OHLCV snapshot ships as a SQLite file so
  backtesting works offline; it is public market data, not secrets.

## Documentation

- [`docs/SYSTEM_FLOW.md`](./docs/SYSTEM_FLOW.md) — system flow and architecture
- [`docs/ALERT_BASED_TRADING_SYSTEM.md`](./docs/ALERT_BASED_TRADING_SYSTEM.md) — alert system details
- [`docs/api/`](./docs/api/) — per-module API notes
- [`docs/dev/`](./docs/dev/) — internal development notes & research (not needed for normal use)

## License

Released under the [MIT License](./LICENSE).

## Disclaimer

This software is provided for **educational and research purposes only**. It is a
paper-trading / simulation system and is **not investment advice**. Trading
financial instruments carries substantial risk of loss. Nothing here is a
recommendation to buy or sell any security. You are solely responsible for any
use of this code, including any configuration for live trading. The authors
accept **no liability** for any financial losses or damages — see the
[LICENSE](./LICENSE) ("AS IS", no warranty).

---

*Built with Groq, Gemini, and Claude for market analysis.*
