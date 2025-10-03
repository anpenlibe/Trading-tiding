"""Provider coordinator managing AI client fallback chain.

This coordinator manages the cascading fallback between AI providers:
Groq (llama-3.3) → Groq (llama-3.1) → Gemini Pro → Rule-based analysis
"""

from typing import Dict, List, Optional, Any
import os
from src.ai.clients.base_client import BaseAIClient
from src.ai.clients.claude_client import ClaudeClient
from src.ai.clients.gemini_client import GeminiClient
from src.ai.clients.groq_client import GroqClient
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'provider_coordinator.log')


class ProviderConfig:
    """Configuration for a single provider in the fallback chain."""

    def __init__(self, provider: str, model: str, max_tokens: int,
                 api_key: Optional[str] = None):
        """Initialize provider configuration.

        Args:
            provider: Provider name ('claude', 'gemini', 'groq')
            model: Model identifier
            max_tokens: Maximum tokens for responses
            api_key: Optional API key override
        """
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = api_key

    def __repr__(self):
        return f"ProviderConfig({self.provider}:{self.model})"


class ProviderCoordinator:
    """Coordinates AI provider fallback chain with per-provider circuit breakers.

    Extracted from ai_brain.py fallback logic (lines 567-641) with enhancements:
    - Per-provider circuit breakers instead of global
    - Multi-model Groq support (separate rate limit pools)
    - Configurable fallback chain
    - Better error tracking and logging
    """

    MAX_CONSECUTIVE_FAILURES = 5

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

        # Current provider tracking
        self.current_provider_index = 0

        logger.info(f"Initialized coordinator with {len(self.fallback_chain)} providers")
        for idx, config in enumerate(self.fallback_chain):
            logger.info(f"  [{idx}] {config}")

    def _get_default_fallback_chain(self) -> List[ProviderConfig]:
        """Get default fallback chain from environment configuration.

        Returns:
            List of provider configurations
        """
        chain = []

        # Groq llama-3.3-70b (first choice - fastest)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            chain.append(ProviderConfig(
                provider="groq",
                model="llama-3.3-70b-versatile",
                max_tokens=3000,  # Conservative for 6000 TPM limit
                api_key=groq_key
            ))

            # Groq llama-3.1-70b (second choice - separate rate limit pool)
            chain.append(ProviderConfig(
                provider="groq",
                model="llama-3.1-70b-versatile",
                max_tokens=3000,
                api_key=groq_key
            ))

        # Gemini Pro (reliable but slower)
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            chain.append(ProviderConfig(
                provider="gemini",
                model="gemini-2.5-pro",
                max_tokens=16000,
                api_key=gemini_key
            ))

        # Claude (premium option if configured)
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if claude_key:
            chain.append(ProviderConfig(
                provider="claude",
                model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "8000")),
                api_key=claude_key
            ))

        if not chain:
            logger.warning("No API keys configured - coordinator will use rule-based fallback only")

        return chain

    def _get_or_create_client(self, config: ProviderConfig) -> BaseAIClient:
        """Get existing client or create new one for provider config.

        Args:
            config: Provider configuration

        Returns:
            BaseAIClient instance
        """
        # Use provider:model as unique key for per-model rate limiting
        key = f"{config.provider}:{config.model}"

        if key in self.clients:
            return self.clients[key]

        # Create new client
        logger.debug(f"Creating new client for {key}")

        if config.provider == "claude":
            client = ClaudeClient(
                api_key=config.api_key,
                model=config.model,
                max_tokens=config.max_tokens,
                temperature=self.temperature
            )
        elif config.provider == "gemini":
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
        key = f"{config.provider}:{config.model}"
        return self.circuit_open.get(key, False)

    def _record_success(self, config: ProviderConfig):
        """Record successful API call, reset failure counter.

        Args:
            config: Provider configuration
        """
        key = f"{config.provider}:{config.model}"
        self.consecutive_failures[key] = 0
        self.circuit_open[key] = False

    def _record_failure(self, config: ProviderConfig):
        """Record failed API call, potentially open circuit breaker.

        Args:
            config: Provider configuration
        """
        key = f"{config.provider}:{config.model}"
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
        # Try each provider in fallback chain
        for idx, config in enumerate(self.fallback_chain):
            # Skip if circuit breaker is open
            if self._is_circuit_open(config):
                logger.debug(f"Skipping {config} - circuit breaker open")
                continue

            try:
                client = self._get_or_create_client(config)

                # Log provider switch
                if idx != self.current_provider_index:
                    logger.info(f"Switching provider: {self.fallback_chain[self.current_provider_index]} → {config}")
                    self.current_provider_index = idx

                # Use config's max_tokens unless overridden
                tokens = max_tokens or config.max_tokens

                logger.debug(f"Calling {config} with max_tokens={tokens}")
                response = client.call_api(prompt, max_tokens=tokens)

                # Success! Reset failure counter
                self._record_success(config)

                return response

            except Exception as e:
                error_msg = str(e)

                # Check if it's a rate limit error
                is_rate_limit = (
                    "429" in error_msg or
                    "rate limit" in error_msg.lower() or
                    "too many requests" in error_msg.lower()
                )

                if is_rate_limit:
                    logger.warning(f"Rate limit hit for {config}: {error_msg}")
                else:
                    logger.error(f"Error from {config}: {error_msg}")

                # Record failure
                self._record_failure(config)

                # Try next provider in chain
                continue

        # All providers failed - return rule-based response
        logger.warning("All AI providers exhausted, using rule-based fallback")
        return self._rule_based_fallback(prompt)

    def _rule_based_fallback(self, prompt: str) -> str:
        """Generate rule-based response when all providers fail.

        Args:
            prompt: The original prompt

        Returns:
            str: Conservative rule-based analysis
        """
        logger.info("Generating rule-based fallback response")

        # This is a placeholder - actual implementation should parse prompt
        # and return appropriate rule-based response
        return "NEUTRAL (rule-based fallback - all AI providers unavailable)"

    def get_current_provider(self) -> Optional[str]:
        """Get name of currently active provider.

        Returns:
            Provider name or None if using rule-based
        """
        if 0 <= self.current_provider_index < len(self.fallback_chain):
            config = self.fallback_chain[self.current_provider_index]
            return f"{config.provider}:{config.model}"
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
