# AI Module — Multi-Provider Fallback Architecture

Robust multi-provider AI decisioning with automatic fallback and per-model rate
limiting. Providers: **Groq** and **Gemini** (both over REST — no provider SDK).
Claude was removed.

## Architecture Overview

```
┌───────────────────────────────────────────────┐
│                    AIBrain                     │
│             src/decision/engine.py             │
│  general pass  ·  consolidated alert review    │
└───────────────────────┬────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              ProviderCoordinator               │
│           src/decision/providers.py            │
│  - Builds fallback chain from env + key pools  │
│  - Per-(provider:model) circuit breakers       │
│  - Rate-limit cooldown + automatic switching   │
└───────────────────────┬────────────────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        ┌──────────┐        ┌──────────┐
        │   Groq   │        │  Gemini  │
        │  Client  │        │  Client  │
        └──────────┘        └──────────┘
```

## Default Fallback Chain

Built from environment config — a provider is included only if it has at least
one key AND appears in `ENABLED_AI_PROVIDERS` (default `groq,gemini`):

1. **Groq `openai/gpt-oss-120b`** (primary — best quality + capacity)
2. **Groq `llama-3.3-70b-versatile`** (separate rate-limit pool)
3. **Groq `openai/gpt-oss-20b`** (fast fallback)
4. **Gemini `gemini-2.5-pro`** (reliable but slower)
5. **Rule-based** (final fallback — RSI-based, no API call; `decision/fallback.py`)

## API Keys (numbered pools)

Keys are read from numbered pools in `.env`, with the singular name as a fallback:

```bash
GROQ_API_KEY_1=...    GROQ_API_KEY_2=...    # (GROQ_API_KEY also accepted)
GEMINI_API_KEY_1=...  GEMINI_API_KEY_2=...  # (GEMINI_API_KEY also accepted)
```

Keys are a **mode-aware pool** (`decision/keys.py`): **key 1 for live**, **keys 2-4
for backtest** (disjoint, so a backtest can't starve the live session). The
coordinator round-robins the starting key per call and paces calls per provider to
stay under the free-tier TPM ceiling.

## Key Features

- **Multi-model Groq**: each Groq model has a separate rate-limit pool, giving
  independent capacity before the chain moves on to Gemini.
- **Per-(provider:model) circuit breakers**: 5 consecutive failures opens a
  breaker; rate-limit (429) errors use a 65s cooldown instead of the breaker.
- **Rule-based fallback**: when all providers are exhausted, `call_with_fallback`
  raises `AIAnalysisError` so `AIBrain` applies its schema-aware RSI fallback.

## Module Structure

```
src/decision/
├── README.md                  # This file
├── engine.py                  # AIBrain — general pass + consolidated alert review
├── prompts.py                 # Prompt construction + response parsing (PromptBuilder)
├── providers.py               # Fallback coordination + provider chains
├── keys.py                    # Mode-aware numbered key pools
├── fallback.py                # Rule-based RSI fallback (no API call)
└── clients/                   # base · groq · gemini REST clients
```

## Usage

```python
from src.decision.engine import AIBrain

ai = AIBrain(mode="backtest")
# General pass — all symbols at once, reasoning-first (the primary entry point):
result = ai.analyze_portfolio_with_intelligent_fallback(portfolio_data, portfolio_indicators, context)
# Consolidated alert review — open positions (manage) + surfaced candidates (consider):
review = ai.analyze_alert_review(portfolio_data, portfolio_indicators, owned, candidates, context)
```

```python
from src.decision.providers import ProviderCoordinator
coord = ProviderCoordinator()
coord.get_current_provider()   # e.g. "groq:openai/gpt-oss-120b"
coord.get_status()             # failures + circuit-breaker state
coord.reset_all_circuits()     # after resolving systemic issues
```

## Environment Configuration

```bash
# At least one Groq or Gemini key must be set (singular or numbered pool).
GROQ_API_KEY_1=your-groq-key
GEMINI_API_KEY_1=your-gemini-key

# Provider allowlist — a provider is used only if listed AND a key is set.
ENABLED_AI_PROVIDERS=groq,gemini
```

Groq and Gemini models are **fixed** in the chain builders (`providers.build_portfolio_chain`
/ `build_symbol_chain`) — no `GROQ_MODEL`/`GEMINI_MODEL` knobs; temperature is set in
code via `AIBrain(temperature=...)`.

## Notes on rate limits
- Groq portfolio calls cap `max_tokens` to stay within the per-model TPM limit.
- On a 429, the offending `(provider:model)` goes into a 65s cooldown and the
  chain advances to the next entry (next Groq model, then Gemini).

## References
- [Groq API Docs](https://console.groq.com/docs)
- [Gemini API Docs](https://ai.google.dev/docs)
