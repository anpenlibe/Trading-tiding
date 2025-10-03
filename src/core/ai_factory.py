"""
AI Provider Factory - Creates the AI brain with multi-provider fallback.

Note: After 2025-10-03 refactor, AIBrain handles all providers internally
via ProviderCoordinator. This factory is maintained for backward compatibility.
"""

from typing import Optional
from src.interfaces import BaseDecisionModel
from src.utils.logger import setup_logger

logger = setup_logger(__name__, 'ai_factory.log')


def create_ai_brain(api_key: Optional[str] = None) -> BaseDecisionModel:
    """
    Create AI brain with multi-provider fallback support.

    Args:
        api_key: Deprecated (kept for backward compatibility, now ignored)

    Returns:
        BaseDecisionModel: AIBrain with automatic provider fallback
    """
    from src.core.ai_brain import AIBrain

    logger.info("Creating AI brain with multi-provider fallback")
    return AIBrain(api_key=api_key)


def get_ai_provider_name() -> str:
    """
    Get current AI provider name.

    Note: After refactor, this returns the primary provider, but AIBrain
    actually uses a fallback chain of multiple providers.
    """
    # Try to get from coordinator if brain is instantiated
    try:
        from src.core.ai_brain import AIBrain
        brain = AIBrain()
        return brain.coordinator.get_current_provider() or "multi-provider"
    except:
        return "multi-provider"


def validate_ai_configuration() -> bool:
    """
    Validate that at least one AI provider is properly configured.

    Returns:
        bool: True if at least one provider has valid API key
    """
    from src.data.config import ANTHROPIC_API_KEY, GEMINI_API_KEY, GROQ_API_KEY

    has_groq = bool(GROQ_API_KEY and GROQ_API_KEY != "your-groq-api-key-here")
    has_gemini = bool(GEMINI_API_KEY and GEMINI_API_KEY != "your-gemini-api-key-here")
    has_claude = bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-claude-api-key-here")

    return has_groq or has_gemini or has_claude