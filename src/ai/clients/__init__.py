"""AI client implementations for different providers.

This module provides a unified interface for interacting with different AI providers:
- Gemini (Google, REST)
- Groq (OpenAI-compatible, REST)

All clients inherit from BaseAIClient and provide consistent rate limiting,
error handling, and API call semantics.
"""

from src.ai.clients.base_client import BaseAIClient
from src.ai.clients.gemini_client import GeminiClient
from src.ai.clients.groq_client import GroqClient

__all__ = [
    'BaseAIClient',
    'GeminiClient',
    'GroqClient',
]
