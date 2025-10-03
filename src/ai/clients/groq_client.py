"""Groq API client implementation using OpenAI-compatible API."""

from typing import Optional
import requests
from src.ai.clients.base_client import BaseAIClient
from src.exceptions import ConfigurationError
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'groq_client.log')


class GroqClient(BaseAIClient):
    """Client for Groq API using OpenAI-compatible endpoint.

    Extracted from ai_brain.py lines 115-128 (init) and 419-458 (API call).

    Key Enhancement: Supports multiple Groq models with separate rate limit tracking.
    Each model (llama-3.3-70b, llama-3.1-70b, etc.) has its own rate limit pool,
    allowing us to use them as independent fallback options.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int, temperature: float):
        """Initialize Groq client.

        Args:
            api_key: Groq API key
            model: Groq model name (e.g., "llama-3.3-70b-versatile", "llama-3.1-70b-versatile")
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
        """
        super().__init__(api_key, model, max_tokens, temperature)

        if not self.api_key:
            raise ConfigurationError("GROQ_API_KEY not configured")

        # Use OpenAI-compatible REST API
        self.client = "rest_api"  # Flag to indicate REST usage
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def call_api(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Make Groq API call via OpenAI-compatible endpoint.

        Args:
            prompt: The prompt to send
            max_tokens: Override default max_tokens

        Returns:
            str: Groq's text response

        Raises:
            Exception: If API call fails or response parsing fails
        """
        self.enforce_rate_limit()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        logger.debug(f"Making Groq API call: model={self.model}, max_tokens={max_tokens or self.max_tokens}")

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=90)
            logger.debug(f"Groq API response status: {response.status_code}")
            response.raise_for_status()

            result = response.json()

            # Parse OpenAI-compatible response
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")

                # For reasoning models (like gpt-oss-20b), check reasoning field if content is empty
                if not content:
                    reasoning = message.get("reasoning", "")
                    if reasoning:
                        logger.debug(f"Using reasoning field from {self.model} (reasoning model)")
                        content = reasoning

                if content:
                    # Strip markdown code blocks if present (common with reasoning models)
                    content = self._strip_markdown_code_blocks(content)
                    return content
                else:
                    raise Exception(f"No content in Groq response: {result}")
            else:
                raise Exception(f"No valid choices in Groq response: {result}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Groq API error: {e}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Groq response: {e}")

    def _strip_markdown_code_blocks(self, content: str) -> str:
        """Strip markdown code blocks from response.

        Many models (especially reasoning models like gpt-oss-120b) wrap
        JSON responses in markdown code blocks like:
        ```json
        {...}
        ```

        This strips those blocks to return clean JSON.

        Args:
            content: Raw response content

        Returns:
            Content with markdown code blocks stripped
        """
        content = content.strip()

        # Check if wrapped in code blocks
        if content.startswith('```'):
            # Find the first newline (end of opening fence)
            first_newline = content.find('\n')
            if first_newline != -1:
                # Find the closing fence
                closing_fence = content.rfind('```')
                if closing_fence > first_newline:
                    # Extract content between fences
                    content = content[first_newline + 1:closing_fence].strip()

        return content

    def get_provider_name(self) -> str:
        """Return 'groq' with model identifier for better tracking."""
        # Include model name for per-model tracking
        return f"groq:{self.model}"

    def _get_rate_limit_delay(self) -> float:
        """Groq has strict rate limits, need conservative delay.

        Free tier: 30 RPM = 1 call per 2 seconds
        Using 10s delay to account for TPM limits and rolling windows.
        """
        return 10.0  # 10 seconds between calls (6 calls/minute)

    def get_rate_limits(self) -> dict:
        """Return Groq free tier rate limits.

        Note: These are PER-MODEL limits. Each model has separate quotas,
        which is why we can use llama-3.3 and llama-3.1 as independent
        fallback options.
        """
        return {
            "RPM": 30,  # Requests per minute
            "TPM": 6000,  # Tokens per minute (prompt + response)
            "RPD": 1000,  # Requests per day
        }

    def supports_model(self, model_name: str) -> bool:
        """Check if this client's model matches the given name.

        Useful for coordinator to verify client configuration.
        """
        return self.model == model_name
