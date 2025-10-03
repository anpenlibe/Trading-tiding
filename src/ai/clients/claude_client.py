"""Claude API client implementation."""

from typing import Optional
import anthropic
from src.ai.clients.base_client import BaseAIClient
from src.exceptions import ConfigurationError


class ClaudeClient(BaseAIClient):
    """Client for Claude AI API using Anthropic SDK.

    Extracted from ai_brain.py lines 92-102 (init) and 310-318 (API call).
    """

    def __init__(self, api_key: str, model: str, max_tokens: int, temperature: float):
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key
            model: Claude model name (e.g., "claude-3-5-sonnet-20241022")
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
        """
        super().__init__(api_key, model, max_tokens, temperature)

        if not self.api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY not configured")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def call_api(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Make Claude API call.

        Args:
            prompt: The prompt to send
            max_tokens: Override default max_tokens

        Returns:
            str: Claude's text response

        Raises:
            Exception: If API call fails
        """
        self.enforce_rate_limit()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0
        )

        return response.content[0].text

    def get_provider_name(self) -> str:
        """Return 'claude'."""
        return "claude"

    def _get_rate_limit_delay(self) -> float:
        """Claude has generous rate limits, minimal delay needed."""
        return 0.5  # 500ms safety margin

    def get_rate_limits(self) -> dict:
        """Return Claude rate limits (tier-dependent, these are conservative)."""
        return {
            "RPM": 50,  # Conservative estimate
            "TPM": 40000,  # Conservative estimate for tier 1
        }
