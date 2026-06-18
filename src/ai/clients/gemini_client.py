"""Gemini API client implementation using REST API."""

import re
from typing import Optional
import requests
from src.ai.clients.base_client import BaseAIClient
from src.exceptions import ConfigurationError
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'gemini_client.log')


class GeminiClient(BaseAIClient):
    """Client for Google Gemini via the REST API (more reliable than the SDK
    in production, and keeps the API key out of logged URLs — see call_api)."""

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

        # Pass the API key via header, NOT the URL query string, so it can never
        # leak into logged URLs or exception messages (requests includes the full
        # URL — query string and all — in HTTPError text).
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=90)
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
            # Defense in depth: even though the key now travels in a header,
            # scrub anything key-shaped before the message reaches a logger.
            msg = re.sub(r"key=[\w.\-]+", "key=***", str(e))
            if self.api_key:
                msg = msg.replace(self.api_key, "***")
            raise Exception(f"Gemini REST API error: {msg}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse Gemini response: {e}")

    def get_provider_name(self) -> str:
        """Return 'gemini'."""
        return "gemini"

    def _get_rate_limit_delay(self) -> float:
        """Gemini's per-model limits are generous (Flash 15 RPM / Pro 2 RPM);
        a small 500ms margin is enough — the coordinator handles 429 cooldowns."""
        return 0.5  # 500ms safety margin
