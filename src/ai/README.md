# AI Module — Multi-Provider Fallback Architecture

Robust multi-provider AI decisioning with automatic fallback and per-model rate
limiting. Providers: **Groq** and **Gemini** (both over REST — no provider SDK).
Claude was removed.

## Architecture Overview

```
┌───────────────────────────────────────────────┐
│                    AIBrain                     │
│              src/core/ai_brain.py              │
│   analyze() (single) / analyze_portfolio_*()   │
└───────────────────────┬────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              ProviderCoordinator               │
│         src/ai/provider_coordinator.py         │
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
5. **Rule-based** (final fallback — RSI-based, no API call; lives in `ai_brain.py`)

## API Keys (numbered pools)

Keys are read from numbered pools in `.env`, with the singular name as a fallback:

```bash
GROQ_API_KEY_1=...    GROQ_API_KEY_2=...    # (GROQ_API_KEY also accepted)
GEMINI_API_KEY_1=...  GEMINI_API_KEY_2=...  # (GEMINI_API_KEY also accepted)
```

`_collect_provider_keys()` gathers `PROVIDER_API_KEY` + `PROVIDER_API_KEY_1..N`,
de-duplicated. **Phase 1 uses the first available key per provider**; full
per-call cycling across the pool (1 key live / 3 keys backtest) is a later phase.

## Key Features

- **Multi-model Groq**: each Groq model has a separate rate-limit pool, giving
  independent capacity before the chain moves on to Gemini.
- **Per-(provider:model) circuit breakers**: 5 consecutive failures opens a
  breaker; rate-limit (429) errors use a 65s cooldown instead of the breaker.
- **Rule-based fallback**: when all providers are exhausted, `call_with_fallback`
  raises `AIAnalysisError` so `AIBrain` applies its schema-aware RSI fallback.

## Module Structure

```
src/ai/
├── README.md                  # This file
├── clients/
│   ├── base_client.py         # Abstract BaseAIClient
│   ├── gemini_client.py       # Gemini REST client
│   └── groq_client.py         # Groq OpenAI-compatible REST client
├── provider_coordinator.py    # Fallback coordination + key pools
└── prompt_builder.py          # Prompt construction + response parsing
```

## Usage

```python
from src.core.ai_brain import AIBrain

ai = AIBrain()
# Portfolio (all symbols at once — the path backtest uses):
result = ai.analyze_portfolio_with_intelligent_fallback(portfolio_data, portfolio_indicators, context)
# Single symbol:
decision = ai.analyze(market_data_df, indicators)
```

```python
from src.ai.provider_coordinator import ProviderCoordinator
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

Groq and Gemini models are **fixed** in `_get_default_fallback_chain` (no
`GROQ_MODEL`/`GEMINI_MODEL` knobs); temperature is set in code via
`AIBrain(temperature=...)`.

## Notes on rate limits
- Groq portfolio calls cap `max_tokens` to stay within the per-model TPM limit.
- On a 429, the offending `(provider:model)` goes into a 65s cooldown and the
  chain advances to the next entry (next Groq model, then Gemini).

## References
- [Groq API Docs](https://console.groq.com/docs)
- [Gemini API Docs](https://ai.google.dev/docs)
