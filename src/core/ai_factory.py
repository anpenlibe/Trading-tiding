"""
AI Provider Factory - Creates the appropriate AI brain based on configuration.

This factory pattern allows switching between different AI providers (Claude, Gemini)
without changing imports or code in consumer modules.
"""

from typing import Optional
from src.interfaces import BaseDecisionModel
from src.data.config import AI_PROVIDER, ANTHROPIC_API_KEY, GEMINI_API_KEY
from src.utils.logger import setup_logger
from src.exceptions import ConfigurationError

logger = setup_logger(__name__, 'ai_factory.log')


def create_ai_brain(api_key: Optional[str] = None) -> BaseDecisionModel:
    """
    Create appropriate AI brain based on configuration.

    Args:
        api_key: Optional API key override

    Returns:
        BaseDecisionModel: Configured AI provider (Claude or Gemini)

    Raises:
        ConfigurationError: If provider is unknown or not properly configured
    """
    provider = AI_PROVIDER.lower()

    if provider == "claude":
        from src.core.ai_brain import ClaudeAI
        logger.info("Creating Claude AI brain")
        return ClaudeAI(api_key=api_key)

    elif provider == "gemini":
        from src.core.gemini_brain import GeminiAI
        logger.info("Creating Gemini AI brain")
        return GeminiAI(api_key=api_key)

    else:
        raise ConfigurationError(f"Unknown AI provider: {provider}. Supported: claude, gemini")


def get_ai_provider_name() -> str:
    """Get current AI provider name."""
    return AI_PROVIDER


def validate_ai_configuration() -> bool:
    """
    Validate that the current AI provider is properly configured.

    Returns:
        bool: True if configuration is valid
    """
    provider = AI_PROVIDER.lower()

    if provider == "claude":
        return bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-claude-api-key-here")
    elif provider == "gemini":
        return bool(GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here")
    else:
        return False