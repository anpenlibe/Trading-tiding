"""Gemini API client implementation using REST API."""

from typing import Optional
import requests
from src.ai.clients.base_client import BaseAIClient
from src.exceptions import ConfigurationError
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'gemini_client.log')


class GeminiClient(BaseAIClient):
    """Client for Google Gemini API using REST API.

    Extracted from ai_brain.py lines 103-114 (init) and 361-417 (API call).
    Uses REST API which has proven more reliable than SDK in production.
    """

    def __init__(self, api_key: str, model: str, max_tokens: int, temperature: float):
        """Initialize Gemini client.

        Args:
            api_key: Google AI API key
            model: Gemini model name (e.g., "gemini-2.5-pro", "gemini-2.5-flash")
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
        """
        super().__init__(api_key, model, max_tokens, temperature)

        if not self.api_key:
            raise ConfigurationError("GEMINI_API_KEY not configured")

        # Use REST API (proven working method)
        self.client = "rest_api"  # Flag to indicate REST usage

    def call_api(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """Make Gemini API call via REST.

        Args:
            prompt: The prompt to send
            max_tokens: Override default max_tokens

        Returns:
            str: Gemini's text response

        Raises:
            Exception: If API call fails or response parsing fails
        """
        self.enforce_rate_limit()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_tokens or self.max_tokens,
                "candidateCount": 1
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        params = {
            "key": self.api_key
        }

        try:
            response = requests.post(url, json=payload, headers=headers, params=params, timeout=90)
            response.raise_for_status()

            result = response.json()

            # Parse response structure
            if "candidates" in result and len(result["candidates"]) > 0:
                candidate = result["candidates"][0]
                if "content" in candidate:
                    content = candidate["content"]
                    # Handle both structures: with and without parts array
                    if "parts" in content and len(content["parts"]) > 0:
                        return content["parts"][0]["text"]
                    elif "text" in content:
                        return content["text"]
                    else:
                        # Fallback: try to find text anywhere in content
                        logger.debug(f"Unexpected content structure: {content}")
                        raise Exception(f"No text found in content: {content}")
                else:
                    raise Exception(f"No content in candidate: {candidate}")
            else:
                raise Exception(f"No valid candidates in response: {result}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Gemini REST API error: {e}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini response: {e}")

    def get_provider_name(self) -> str:
        """Return 'gemini'."""
        return "gemini"

    def _get_rate_limit_delay(self) -> float:
        """Gemini has model-specific rate limits, minimal delay."""
        return 0.5  # 500ms safety margin

    def get_rate_limits(self) -> dict:
        """Return Gemini rate limits (model-dependent).

        Flash models: 15 RPM free tier
        Pro models: 2 RPM free tier
        """
        if "flash" in self.model.lower():
            return {
                "RPM": 15,
                "TPM": 1000000,  # 1M TPM for flash
            }
        else:  # Pro models
            return {
                "RPM": 2,
                "TPM": 32000,  # 32k per request
            }
