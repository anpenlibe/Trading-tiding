"""Provider coordinator managing AI client fallback chain.

This coordinator manages the cascading fallback between AI providers:
Groq (gpt-oss-120b) → Groq (llama-3.3-70b) → Groq (gpt-oss-20b) → Gemini Pro → Rule-based

Keys come from numbered pools in .env (GROQ_API_KEY_1..N, GEMINI_API_KEY_1..N).

Rate limits (per Groq model):
- gpt-oss-120b: 8K TPM, 200K TPD (primary - best quality + capacity)
- llama-3.3-70b: 6K TPM, 100K TPD (proven reliable)
- gpt-oss-20b: 8K TPM, 200K TPD (fast fallback)
Combined Groq capacity: 500K TPD
"""

from typing import Dict, List, Optional, Any
import os
import time
import threading
from src.decision.clients.base_client import BaseAIClient
from src.decision.clients.gemini_client import GeminiClient
from src.decision.clients.groq_client import GroqClient
from src.platform.config import AI_CALL_MIN_INTERVAL_SEC, RATE_LIMIT_COOLDOWN_SEC
from src.platform.logger import setup_logger
from src.platform.errors import AIAnalysisError
from src.platform.events import log_event
from src.decision.keys import provider_keys

logger = setup_logger(__name__, 'provider_coordinator.log')

# Module-level pacer shared across ALL coordinators: the portfolio (general) and
# symbol (special) chains both hit the same provider accounts, so spacing must be
# global per provider, not per coordinator. Reserves a time slot under the lock,
# then sleeps outside it.
_pace_lock = threading.Lock()
_last_call_at: Dict[str, float] = {}


def _pace(provider: str, min_interval: float):
    """Block until at least ``min_interval`` s have passed since the last call to
    ``provider`` (across every coordinator). No-op when the interval is 0."""
    if min_interval <= 0:
        return
    with _pace_lock:
        target = max(time.time(), _last_call_at.get(provider, 0.0) + min_interval)
        _last_call_at[provider] = target
    wait = target - time.time()
    if wait > 0:
        time.sleep(wait)


class ProviderConfig:
    """Configuration for a single provider in the fallback chain."""

    def __init__(self, provider: str, model: str, max_tokens: int,
                 api_key: Optional[str] = None, key_id: int = 0):
        """Initialize provider configuration.

        Args:
            provider: Provider name ('gemini', 'groq')
            model: Model identifier
            max_tokens: Maximum tokens for responses
            api_key: Optional API key override
            key_id: Index of this config's key within the provider's pool, so the
                same model on different keys cools/cycles independently.
        """
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key
        self.key_id = key_id

    def __repr__(self):
        return f"ProviderConfig({self.provider}:{self.model}#{self.key_id})"


class ProviderCoordinator:
    """Coordinates AI provider fallback chain with per-provider circuit breakers.

    Extracted from ai_brain.py fallback logic (lines 567-641) with enhancements:
    - Per-provider circuit breakers instead of global
    - Multi-model Groq support (separate rate limit pools)
    - Configurable fallback chain
    - Better error tracking and logging
    """

    MAX_CONSECUTIVE_FAILURES = 5
    RATE_LIMIT_COOLDOWN = RATE_LIMIT_COOLDOWN_SEC  # benched seconds after a 429 (config)

    def __init__(self, fallback_chain: Optional[List[ProviderConfig]] = None,
                 temperature: float = 0.6):
        """Initialize provider coordinator.

        Args:
            fallback_chain: List of provider configurations in fallback order
            temperature: Sampling temperature for all providers
        """
        self.temperature = temperature
        self.fallback_chain = fallback_chain or self._get_default_fallback_chain()

        # Per-provider tracking
        self.clients: Dict[str, BaseAIClient] = {}
        self.consecutive_failures: Dict[str, int] = {}
        self.circuit_open: Dict[str, bool] = {}
        self.rate_limit_cooldown: Dict[str, float] = {}  # Track rate limit cooldown (timestamp when available again)

        # Current provider tracking (by entity, since the per-call attempt order
        # is rotated — an index into the static chain would be misleading).
        self.current_entity: Optional[str] = None

        # Round-robin: chain grouped into same-model key-runs, plus a call counter.
        # Each call rotates the starting key WITHIN each model's group, so repeated
        # calls spread across all of a model's keys instead of always hammering key 0
        # and only moving on after it 429s. Model priority order is preserved.
        self._groups = self._group_chain(self.fallback_chain)
        self._call_count = 0

        logger.info(f"Initialized coordinator with {len(self.fallback_chain)} providers")
        for idx, config in enumerate(self.fallback_chain):
            logger.info(f"  [{idx}] {config}")

    def _get_default_fallback_chain(self) -> List[ProviderConfig]:
        """Default when no chain is supplied: the single-symbol chain in backtest
        mode. AIBrain normally builds explicit portfolio/symbol chains instead."""
        return build_symbol_chain("backtest")

    @staticmethod
    def _group_chain(chain: List[ProviderConfig]) -> List[List[ProviderConfig]]:
        """Split the flat chain into consecutive same-(provider,model) key-runs,
        preserving order. Keys for one model are contiguous (built by `_expand`),
        so each group is exactly that model's key pool — the unit we round-robin."""
        groups: List[List[ProviderConfig]] = []
        for cfg in chain:
            if groups and (cfg.provider, cfg.model) == (groups[-1][0].provider, groups[-1][0].model):
                groups[-1].append(cfg)
            else:
                groups.append([cfg])
        return groups

    def _attempt_order(self) -> List[ProviderConfig]:
        """The chain for THIS call: each model's keys rotated by the call counter so
        successive calls start on a different key. Model priority order is kept; on
        failure the loop still falls through every remaining key and model."""
        rot = self._call_count
        order: List[ProviderConfig] = []
        for group in self._groups:
            n = len(group)
            start = rot % n  # no-op for single-key groups (e.g. live = 1 key)
            order += group[start:] + group[:start]
        return order

    @staticmethod
    def _entity(config: ProviderConfig) -> str:
        """Unique id per (provider, model, key) so each key cools/cycles
        independently — cycling a model's keys is just advancing through its
        same-model entries in the chain."""
        return f"{config.provider}:{config.model}#{config.key_id}"

    def _get_or_create_client(self, config: ProviderConfig) -> BaseAIClient:
        """Get existing client or create new one for provider config.

        Args:
            config: Provider configuration

        Returns:
            BaseAIClient instance
        """
        # Use provider:model as unique key for per-model rate limiting
        key = self._entity(config)

        if key in self.clients:
            return self.clients[key]

        # Create new client
        logger.debug(f"Creating new client for {key}")

        if config.provider == "gemini":
            client = GeminiClient(
                api_key=config.api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=self.temperature
            )
        elif config.provider == "groq":
            client = GroqClient(
                api_key=config.api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=self.temperature
            )
        else:
            raise ValueError(f"Unknown provider: {config.provider}")

        self.clients[key] = client
        self.consecutive_failures[key] = 0
        self.circuit_open[key] = False

        return client

    def _is_circuit_open(self, config: ProviderConfig) -> bool:
        """Check if circuit breaker is open for provider.

        Args:
            config: Provider configuration

        Returns:
            True if circuit is open (too many failures)
        """
        key = self._entity(config)
        return self.circuit_open.get(key, False)

    def _is_rate_limited(self, config: ProviderConfig) -> bool:
        """Check if provider is in rate limit cooldown.

        Args:
            config: Provider configuration

        Returns:
            True if still in cooldown period
        """
        key = self._entity(config)
        cooldown_until = self.rate_limit_cooldown.get(key, 0)

        if cooldown_until > time.time():
            remaining = int(cooldown_until - time.time())
            logger.debug(f"Provider {key} in rate limit cooldown ({remaining}s remaining)")
            return True

        return False

    def _set_rate_limit_cooldown(self, config: ProviderConfig):
        """Put provider in rate limit cooldown.

        Args:
            config: Provider configuration
        """
        key = self._entity(config)
        cooldown_until = time.time() + self.RATE_LIMIT_COOLDOWN
        self.rate_limit_cooldown[key] = cooldown_until
        logger.info(f"Provider {key} in rate limit cooldown for {self.RATE_LIMIT_COOLDOWN}s")

    def _record_success(self, config: ProviderConfig):
        """Record successful API call, reset failure counter.

        Args:
            config: Provider configuration
        """
        key = self._entity(config)
        self.consecutive_failures[key] = 0
        self.circuit_open[key] = False

    def _record_failure(self, config: ProviderConfig):
        """Record failed API call, potentially open circuit breaker.

        Args:
            config: Provider configuration
        """
        key = self._entity(config)
        self.consecutive_failures[key] = self.consecutive_failures.get(key, 0) + 1

        if self.consecutive_failures[key] >= self.MAX_CONSECUTIVE_FAILURES:
            logger.warning(f"Circuit breaker OPEN for {key} after {self.consecutive_failures[key]} failures")
            self.circuit_open[key] = True

    def call_with_fallback(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Make API call with automatic fallback on failure.

        Tries providers in fallback chain order. On rate limit or error,
        moves to next provider. Returns rule-based response if all fail.

        Args:
            prompt: The prompt to send
            max_tokens: Override default max_tokens

        Returns:
            str: AI response or rule-based fallback
        """
        # Models that returned 413 this pass: skip ALL their keys. 413 is
        # structural (the model rejects this request regardless of key), so
        # cycling keys can't help — drop straight to the next model.
        skip_models = set()

        # Advance the round-robin so this call starts on a different key than the last.
        self._call_count += 1

        for config in self._attempt_order():
            if config.model in skip_models:
                continue
            # Skip if circuit breaker is open
            if self._is_circuit_open(config):
                logger.debug(f"Skipping {config} - circuit breaker open")
                continue

            # Skip if in rate limit cooldown
            if self._is_rate_limited(config):
                continue

            try:
                client = self._get_or_create_client(config)

                # Log provider switch (tracked by entity since attempt order rotates)
                entity = self._entity(config)
                if entity != self.current_entity:
                    if self.current_entity is not None:
                        logger.info(f"Switching provider: {self.current_entity} → {entity}")
                    self.current_entity = entity

                # Use config's max_tokens unless overridden
                tokens = max_tokens or config.max_tokens

                # Proactively space calls to this provider so a burst of special
                # passes doesn't fire into the per-minute limit all at once.
                _pace(config.provider, AI_CALL_MIN_INTERVAL_SEC)

                logger.debug(f"Calling {config} with max_tokens={tokens}")
                response = client.call_api(prompt, max_tokens=tokens)

                # Success! Reset failure counter
                self._record_success(config)

                return response

            except Exception as e:
                error_msg = str(e)

                # 429 = rate limit (per-key TPM): cool THIS (model,key); the chain's
                # next entry for the same model uses a different key (separate bucket).
                is_rate_limit = (
                    "429" in error_msg or
                    "rate limit" in error_msg.lower() or
                    "too many requests" in error_msg.lower()
                )
                # 413 = payload too large (structural, identical for every key of a
                # model): skip the model's remaining keys, fall to the next model.
                is_payload = (
                    "413" in error_msg or
                    "payload too large" in error_msg.lower() or
                    "request too large" in error_msg.lower()
                )

                if is_rate_limit:
                    logger.warning(f"Rate limit hit for {config}: {error_msg}")
                    log_event('rate_limit', provider=str(config))
                    self._set_rate_limit_cooldown(config)
                elif is_payload:
                    logger.warning(f"{config} returned 413 — skipping this model's remaining keys")
                    skip_models.add(config.model)
                else:
                    logger.error(f"Error from {config}: {error_msg}")
                    self._record_failure(config)

                # Try next provider in chain
                continue

        # All providers exhausted (rate-limited or errored). Raise so the caller
        # (AIBrain) applies its schema-aware rule-based fallback — the coordinator
        # cannot know whether a single-symbol or portfolio JSON shape is expected.
        logger.warning("All AI providers exhausted; raising for caller's rule-based fallback")
        raise AIAnalysisError("All AI providers unavailable (rate-limited or failed)")

    def get_current_provider(self) -> Optional[str]:
        """Get name of currently active provider.

        Returns:
            Provider name or None if using rule-based
        """
        # current_entity is "provider:model#key_id"; strip the key for the name.
        if self.current_entity:
            return self.current_entity.rsplit('#', 1)[0]
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status for debugging.

        Returns:
            Dict with coordinator state
        """
        return {
            "current_provider": self.get_current_provider(),
            "fallback_chain": [str(c) for c in self.fallback_chain],
            "failures": dict(self.consecutive_failures),
            "circuit_breakers": dict(self.circuit_open),
        }

    def reset_all_circuits(self):
        """Reset all circuit breakers. Use when resolving systemic issues."""
        logger.info("Resetting all circuit breakers")
        for key in self.circuit_open:
            self.circuit_open[key] = False
            self.consecutive_failures[key] = 0


# ----- chain builders (mode-aware, key-cycled) -----------------------------------
# Two prompt-specific chains. Each model is expanded into one ProviderConfig per
# key in the pool (mode-selected: live=key1, backtest=keys2..N), so the coordinator
# cycles a model's keys before falling to the next model. Build once and pass to a
# ProviderCoordinator.

def _enabled_providers() -> set:
    return {
        p.strip().lower()
        for p in os.getenv("ENABLED_AI_PROVIDERS", "groq,gemini").split(",")
        if p.strip()
    }


def _expand(provider: str, model: str, max_tokens: int, keys: List[str]) -> List[ProviderConfig]:
    """One ProviderConfig per key for (provider, model)."""
    return [ProviderConfig(provider, model, max_tokens, api_key=k, key_id=i)
            for i, k in enumerate(keys)]


def build_portfolio_chain(mode: str = "backtest") -> List[ProviderConfig]:
    """Long all-symbols prompt: Gemini Flash (handles the big prompt; no 413) →
    llama-70b fallback. Both key-cycled."""
    enabled = _enabled_providers()
    chain: List[ProviderConfig] = []
    if "gemini" in enabled:
        chain += _expand("gemini", "gemini-2.5-flash", 16000, provider_keys("GEMINI", mode))
    if "groq" in enabled:
        chain += _expand("groq", "llama-3.3-70b-versatile", 6000, provider_keys("GROQ", mode))
    if not chain:
        logger.warning("Portfolio chain empty — no API keys; rule-based fallback only")
    return chain


def build_symbol_chain(mode: str = "backtest") -> List[ProviderConfig]:
    """Short single-symbol prompt (special pass): best Groq model key-cycled, then
    fallback Groq models key-cycled, then Gemini Flash."""
    enabled = _enabled_providers()
    chain: List[ProviderConfig] = []
    if "groq" in enabled:
        groq_keys = provider_keys("GROQ", mode)
        for model in ("openai/gpt-oss-120b", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"):
            chain += _expand("groq", model, 6000, groq_keys)
    if "gemini" in enabled:
        chain += _expand("gemini", "gemini-2.5-flash", 16000, provider_keys("GEMINI", mode))
    if not chain:
        logger.warning("Symbol chain empty — no API keys; rule-based fallback only")
    return chain
