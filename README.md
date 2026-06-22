# trading-tiding

**AI-assisted swing-trading research bot for the NSE (Indian equities).**

`trading-tiding` replays (backtest) or streams (live) NSE market data, computes a
rich set of technical features, and asks an LLM for BUY/SELL/HOLD decisions under
explicit risk limits — then simulates the fills. It is an **educational / research
project and a paper-trading simulator — not investment advice.** See the
[disclaimer](#disclaimer) before doing anything with real money.

> **Paper trading only.** Even the live runner places **paper fills on live data** —
> there is no real-money order placement in this codebase.

---

## Highlights

- **Two modes, one core.** A backtest runner (replays the local DB, fast-forward)
  and a live runner (real-time Zerodha data) share the *exact same* decision
  pipeline — they differ only in ingestion and timing.
- **Two-pass AI brain.** A **general pass** scores all symbols at once (Gemini
  Flash), and AI-triggered **special passes** deep-dive a single symbol on an alert
  (fast Groq gpt-oss). The model also emits its own alerts and a watchlist.
- **Intent-driven alerts.** Between general passes the system only wakes on what it
  cares about: held positions are managed by their own stop/target/recheck levels,
  watchlist names by the AI's price conditions, and a technical backstop
  (RSI/MACD/volume) runs on watchlist stocks only — so indicator noise can flag an
  *entry* but never churns an *exit*.
- **Multi-key, rate-limit aware.** Groq + Gemini key *pools* (keys 2-4 in backtest,
  key 1 reserved for live) are round-robined per call and throttled to stay under
  the free-tier tokens-per-minute ceiling, with per-(model,key) circuit breakers and
  a rule-based fallback when everything is exhausted.
- **23 features + market context.** RSI/MACD/SMA plus ATR, Bollinger %B/bandwidth,
  OBV, RSI trajectory, MACD-cross state, Stochastic, ROC, range-position, volume
  trend — fed to the AI alongside **market regime**, **sector**, and **held-position
  context** (entry/P&L/duration).
- **Volatility-aware risk.** ATR-based dynamic stops (per-stock), position sizing
  under a per-position cap, and an affordability check using the **real** Indian-
  equity turnover charge model (STT, exchange, GST, stamp, DP).

---

## Architecture

A clean layered pipeline; the two run modes are thin shells over a shared core.

```
runners/        backtest.py · live.py · download.py        (entry points / modes)
src/
  pipeline.py   TradingPipeline — the shared decide → risk → execute body
  marketdata/   sources (Zerodha) · feed (DatabaseSource / LiveSource) · store ·
                validation · cache · collector · maintenance
  features/     indicators (23 features + market-regime summary)
  decision/     engine (AIBrain) · prompts · providers · keys · fallback · clients/
  risk/         manager (ATR stops, position sizing)
  portfolio/    book (positions, cash, P&L, persistence)
  execution/    executor (paper fills) · costs (turnover charges)
  alerts/       engine · rules · manager
  monitoring/   performance · dashboard
  platform/     config · types · errors · logger · retry · registry · modes
```

**Data flow:** `feed` → `features` → `decision` → `risk` → `execution`, with
`alerts` and `portfolio` feeding context into the decision. The only thing that
differs between backtest and live is the `MarketDataSource` behind the feed
(`DatabaseSource` vs `LiveSource`) and the loop (replay vs wall-clock).

## How it works

1. **Data** — Zerodha Kite Connect is the **sole** source. Backtests read the local
   SQLite DB (`data/market_data.sqlite`); the live runner fetches fresh quotes and
   appends to that DB so indicator history grows. There is no Yahoo or synthetic
   mock fallback — missing data fails loud.
2. **Features** — `calculate_all_indicators(df)` turns an OHLCV frame into a flat
   dict of 23 indicators; a breadth-based market-regime summary is computed across
   symbols.
3. **Decision** — `AIBrain` runs two prompt-specific provider chains: the long
   all-symbols prompt on **Gemini Flash → llama-70b**, and the short single-symbol
   special-pass prompt on **gpt-oss-120b → llama-70b → gpt-oss-20b → Flash**. All
   key-cycled; rule-based RSI fallback if exhausted.
4. **Risk + execution** — `SimpleRiskManager` sets ATR-scaled stops/targets and
   sizes the position; `PaperTrader` records the fill against a `Portfolio` book
   with realistic slippage + turnover charges and tracks P&L.

## Requirements

- **Python 3.10+** (developed on 3.12)
- At least **one** AI provider key — Groq or Gemini (Claude/Anthropic is not used)
- A **Zerodha Kite Connect** account for market data (live *and* to populate the
  backtest DB)

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

All configuration lives in `.env`. The only hard requirement is one AI key.
**Keys are read as numbered pools**, with key 1 reserved for live and keys 2-4
cycled in backtest (so a backtest can't exhaust your live session's rate limit):

```bash
GROQ_API_KEY_1=...   GROQ_API_KEY_2=...   GROQ_API_KEY_3=...   GROQ_API_KEY_4=...
GEMINI_API_KEY_1=... GEMINI_API_KEY_2=... GEMINI_API_KEY_3=... GEMINI_API_KEY_4=...
# (the singular GROQ_API_KEY / GEMINI_API_KEY are accepted as a fallback)

ZERODHA_API_KEY=...  ZERODHA_API_SECRET=...  ZERODHA_ACCESS_TOKEN=...
```

| Variable | Default | Purpose |
|---|---|---|
| `ENABLED_AI_PROVIDERS` | `groq,gemini` | Providers allowed in the chains. |
| `TRADING_STRATEGY` | `swing` | Symbol selection: `conservative`, `swing`, `diversified`, `tech_focus`. |
| `INITIAL_CAPITAL` | `10000.0` | Starting paper capital (₹). |
| `MAX_RISK_PER_TRADE` | `0.015` | Fraction of capital risked per trade. |
| `TRADING_PRODUCT` | `delivery` | Charge schedule: `delivery` or `intraday`. |
| `TRADING_MODE` | `paper` | `paper` / `live` / `backtest`. |

### Zerodha token (daily)

Access tokens expire daily. Refresh via the helper (OAuth flow, writes back to `.env`):

```bash
python scripts/generate_zerodha_token.py
```

## Usage

Run from the repo root.

```bash
# Populate / refresh the local DB from Zerodha (needed before backtesting)
python runners/download.py --period 60d --interval 1d
python runners/download.py --period 60d --interval 1m --symbols RELIANCE TCS

# Backtest (replays the local DB)
python runners/backtest.py --auto                          # last 3 days, daily
python runners/backtest.py --interval 1m --days 5 --speed 100
python runners/backtest.py --general-every 10              # alerts/special passes between general passes
python runners/backtest.py --start-date 2025-09-01 --end-date 2025-09-30

# Live — PAPER fills on live Zerodha data (needs a fresh token + market hours)
python runners/live.py --general-min 90 --alert-min 5
python runners/live.py --ignore-market-hours               # off-hours smoke test
```

## Supported stocks & strategies

The registry (`src/platform/registry.py`) covers NSE stocks across sectors
(Technology, Banking, Energy, FMCG, Pharma, Telecom, Metals, Auto, Infrastructure),
each tagged with market cap, liquidity, and sector. `TRADING_STRATEGY` selects a
subset (`conservative` / `swing` / `diversified` / `tech_focus`). `^NSEI` is added
for market-regime context.

## Safety features

- **Paper trading only** — no real-money order placement exists; the live runner
  simulates fills on live data.
- **Zerodha-only, fail-loud** — no synthetic/mock data; missing data raises rather
  than fabricating bars. A >20% price-jump validator guards the stored history.
- **Risk guards** — ATR-based stops, a per-position cap (% of capital), per-trade
  risk limit, and an affordability check against the real turnover charge model.

## Documentation

- [`src/decision/README.md`](./src/decision/README.md) — the multi-provider AI layer
- Per-module reference: docstrings in `src/` are the single source of truth — the
  general/special-pass + alert design lives in `src/alerts/manager.py` and
  `src/decision/prompts.py` headers.

## Project status

Research / paper-trading. The backtest is the primary, fully-exercised tool; the
live runner places paper fills on live data and is best run during market hours
with a fresh token. There is currently no automated test suite — verification is by
running the backtest and watching behavior. Real-money order placement is
intentionally **out of scope**.

## License

Released under the [MIT License](./LICENSE).

## Disclaimer

This software is for **educational and research purposes only**. It is a
paper-trading / simulation system and is **not investment advice**. Trading carries
substantial risk of loss. You are solely responsible for any use of this code. The
authors accept **no liability** — see the [LICENSE](./LICENSE) ("AS IS", no warranty).

---

*Built with Groq and Gemini for market analysis.*
