# AI Module - Multi-Provider Fallback Architecture

**Refactored: 2025-10-03**

This module provides a robust multi-provider AI system with automatic fallback and per-model rate limiting.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                           AIBrain                                │
│            (ClaudeAI is a deprecated back-compat alias)          │
│                   src/core/ai_brain.py                           │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ProviderCoordinator                            │
│              src/ai/provider_coordinator.py                      │
│  - Manages fallback chain                                        │
│  - Per-provider circuit breakers                                 │
│  - Automatic provider switching on errors                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌─────────┐      ┌──────────┐     ┌──────────┐
    │  Groq   │      │  Gemini  │     │  Claude  │
    │ Client  │      │  Client  │     │  Client  │
    └─────────┘      └──────────┘     └──────────┘
```

## Default Fallback Chain

The exact chain is built from environment config (a provider is included only if
its API key is set and it appears in `ENABLED_AI_PROVIDERS`):

1. **Groq `openai/gpt-oss-120b`** (Primary - best quality + capacity)
2. **Groq `llama-3.3-70b-versatile`** (Secondary - separate rate limit pool)
3. **Groq `openai/gpt-oss-20b`** (Tertiary - fast fallback)
4. **Gemini `gemini-2.5-pro`** (reliable but slower)
5. **Claude `claude-3-5-sonnet`** (premium - if configured)
6. **Rule-based** (final fallback - RSI-based, no API)

## Key Features

### 1. Multi-Model Groq Support
Each Groq model has **separate rate limit pools**, so the three Groq entries
above give independent capacity before the chain moves on to Gemini/Claude.

### 2. Per-Provider Circuit Breakers
Each provider has independent failure tracking:
- Failures on Groq don't affect Gemini's availability
- Circuit resets when switching providers
- Max 5 consecutive failures per provider

### 3. Automatic Rate Limiting
Each client enforces provider-specific rate limits:
- **Groq**: 10s between calls (conservative)
- **Gemini**: 0.5s between calls
- **Claude**: 0.5s between calls

### 4. Backward Compatibility
Existing code has been updated to use `AIBrain()`:
```python
# All apps now use AIBrain
from src.core.ai_brain import AIBrain

ai = AIBrain()
result = ai.analyze_portfolio_with_intelligent_fallback(...)
```

**Note**: Legacy alias `ClaudeAI = AIBrain` is available for backward compatibility with external scripts.

## Module Structure

```
src/ai/
├── README.md                      # This file
├── clients/
│   ├── __init__.py                # Client exports
│   ├── base_client.py             # Abstract base class
│   ├── claude_client.py           # Claude API client
│   ├── gemini_client.py           # Gemini REST API client
│   └── groq_client.py             # Groq OpenAI-compatible client
├── provider_coordinator.py        # Fallback coordination
└── prompt_builder.py              # Prompt construction (unchanged)
```

## Client Implementations

### BaseAIClient (Abstract)
Common interface for all AI providers:
- `call_api(prompt, max_tokens)` - Make API call
- `enforce_rate_limit()` - Rate limit enforcement
- `get_provider_name()` - Provider identifier
- `get_rate_limits()` - Provider rate limits

### ClaudeClient
- Uses Anthropic SDK
- Minimal rate limiting (0.5s)
- Conservative estimate: 50 RPM, 40k TPM

### GeminiClient
- Uses REST API (proven reliable)
- Model-specific limits:
  - Flash models: 15 RPM, 1M TPM
  - Pro models: 2 RPM, 32k TPM

### GroqClient
- Uses OpenAI-compatible REST API
- Per-model tracking via `get_provider_name()` returns `groq:model`
- Conservative 3,000 max_tokens (fits within 6,000 TPM limit)

## Provider Coordinator

### Configuration
```python
# Default fallback chain (from environment)
coordinator = ProviderCoordinator()

# Custom fallback chain
from src.ai.provider_coordinator import ProviderConfig

chain = [
    ProviderConfig("groq", "openai/gpt-oss-120b", 6000),
    ProviderConfig("groq", "llama-3.3-70b-versatile", 6000),
    ProviderConfig("gemini", "gemini-2.5-pro", 16000),
]
coordinator = ProviderCoordinator(fallback_chain=chain)
```

### API Usage
```python
# Simple call with automatic fallback
response = coordinator.call_with_fallback(prompt)

# Check current provider
provider = coordinator.get_current_provider()  # "groq:llama-3.3-70b-versatile"

# Get coordinator status
status = coordinator.get_status()
# {
#   "current_provider": "groq:llama-3.3-70b-versatile",
#   "failures": {"groq:llama-3.3-70b-versatile": 0},
#   "circuit_breakers": {"groq:llama-3.3-70b-versatile": False}
# }

# Reset all circuit breakers (after resolving systemic issues)
coordinator.reset_all_circuits()
```

## Environment Configuration

Required in `.env`:
```bash
# At least one API key must be configured
GROQ_API_KEY=your-groq-key
GEMINI_API_KEY=your-gemini-key
ANTHROPIC_API_KEY=your-anthropic-key  # Optional
```

Configuration (optional overrides):
```bash
# Provider allowlist — a provider is used only if listed AND its key is set
ENABLED_AI_PROVIDERS=groq,gemini,claude

# Claude model / token overrides — the ONLY per-provider knobs read at runtime.
CLAUDE_MODEL=claude-3-5-sonnet-20241022
CLAUDE_MAX_TOKENS=8000
```

The Groq and Gemini models are **fixed** in the coordinator's fallback chain
(`_get_default_fallback_chain`) — there are no `GROQ_MODEL` / `GEMINI_MODEL`
env knobs — and temperature is set in code (`AIBrain(temperature=...)`).

## Rate Limit Handling

### Groq TPM Limit Solution
**Problem**: Requesting 16,000 max_tokens exceeded 6,000 TPM limit

**Solution**: Use 3,000 max_tokens for Groq
```python
# Portfolio prompt ~2,500 tokens
# + Response 3,000 tokens
# = 5,500 total < 6,000 TPM ✓
```

### Multi-Model Fallback
When the primary Groq model (gpt-oss-120b) hits a rate limit:
1. Coordinator catches the rate limit error
2. Switches to the next Groq model (llama-3.3-70b, then gpt-oss-20b — each a
   separate rate pool)
3. If all Groq models are exhausted, falls back to Gemini, then Claude
4. Circuit breakers prevent repeated failures

## Testing

### Basic Import Test
```bash
python3 -c "from src.core.ai_brain import ClaudeAI; print('Success')"
```

### Backtest Integration Test
```bash
# Run short backtest to verify backward compatibility
python3 apps/backtest.py --auto --days 1
```

### Provider Test
```python
from src.ai.provider_coordinator import ProviderCoordinator

coord = ProviderCoordinator()
response = coord.call_with_fallback("What is 2+2?")
print(f"Response from {coord.get_current_provider()}: {response}")
```

## Performance Metrics

### Speed Comparison (20-stock portfolio)
- **Groq llama-3.3**: ~5 seconds ⚡
- **Gemini Flash**: ~30 seconds 🏃
- **Gemini Pro**: ~70 seconds 🐢
- **Claude**: ~15 seconds 🚀

### Capacity
- **Single Groq model**: 30 calls/min, 1,000 calls/day
- **Dual Groq models**: 60 calls/min, 2,000 calls/day
- **With Gemini fallback**: Effectively unlimited for backtesting

## Migration Guide

### Before (Old Architecture)
```python
# ai_brain.py manually handled provider switching
if self.provider == "groq":
    response = self._call_groq_api(prompt)
elif self.provider == "gemini":
    response = self._call_gemini_rest_api(prompt)
```

### After (New Architecture)
```python
# Coordinator handles everything automatically
response = self.coordinator.call_with_fallback(prompt)
```

### Code Changes Required
All application code has been updated to use `AIBrain` instead of the deprecated `ClaudeAI` name.

## Troubleshooting

### All Providers Failing
```python
# Check coordinator status
status = ai.coordinator.get_status()
print(status)

# Reset circuit breakers if needed
ai.coordinator.reset_all_circuits()
```

### Rate Limit Issues
Check logs for provider-specific rate limit hits:
```
2025-10-03 10:15:23 - Rate limit hit for groq:llama-3.3-70b-versatile
2025-10-03 10:15:23 - Switching provider: groq:openai/gpt-oss-120b → groq:llama-3.3-70b-versatile
```

### Circuit Breaker Open
Wait for issue resolution, then:
```python
ai.coordinator.reset_all_circuits()
```

## Future Enhancements

1. **Dynamic Rate Limit Adjustment**: Learn optimal delays from API responses
2. **Provider Health Monitoring**: Track success rates and latency
3. **Smart Provider Selection**: Choose based on task complexity
4. **Response Caching**: Reduce API calls for repeated prompts
5. **Async API Calls**: Parallel requests to multiple providers

## References

- [Groq API Docs](https://console.groq.com/docs)
- [Gemini API Docs](https://ai.google.dev/docs)
- [Claude API Docs](https://docs.anthropic.com/)
