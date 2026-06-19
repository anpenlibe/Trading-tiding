"""Base AI client abstraction for provider-agnostic API calls."""

import time
from abc import ABC, abstractmethod
from typing import Optional
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'ai_clients.log')


class BaseAIClient(ABC):
    """Abstract base class for AI provider API clients.

    Each provider (Gemini, Groq) implements this interface to provide
    a consistent API for making LLM calls with built-in rate limiting and
    error handling.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int, temperature: float):
        """Initialize client with common parameters.

        Args:
            api_key: API key for authentication
            model: Model identifier (e.g., "gemini-2.5-pro", "openai/gpt-oss-120b")
            max_tokens: Default maximum tokens for responses
            temperature: Sampling temperature (0.0 to 1.0)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Rate limiting state
        self.last_api_call_time = 0
        self.rate_limit_delay = self._get_rate_limit_delay()

    @abstractmethod
    def call_api(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Make API call and return text response.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Override default max_tokens for this call

        Returns:
            str: The text response from the LLM

        Raises:
            Exception: If API call fails
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name (e.g., 'gemini', 'groq')."""
        pass

    @abstractmethod
    def _get_rate_limit_delay(self) -> float:
        """Return delay in seconds between API calls for this provider.

        Returns:
            float: Seconds to wait between calls
        """
        pass

    def enforce_rate_limit(self):
        """Sleep just enough to respect this provider's min delay between calls."""
        if self.last_api_call_time == 0:
            self.last_api_call_time = time.time()
            return

        time_since_last_call = time.time() - self.last_api_call_time

        if time_since_last_call < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_call
            logger.debug(f"Rate limiting {self.get_provider_name()}: waiting {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_api_call_time = time.time()

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}(model={self.model})"
