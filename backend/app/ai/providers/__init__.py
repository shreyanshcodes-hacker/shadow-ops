from app.ai.providers.base import (
    AIProvider,
    AIProviderType,
    AIModel,
    AIResponse,
    AIResponseMetadata,
    AIProviderError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderServerError,
    AIProviderValidationError,
    AIProviderRegistry,
    ai_provider_registry,
    get_ai_provider,
    get_ai_provider_for_model,
)

from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.grok import GrokProvider
from app.core.config import settings


def initialize_providers():
    """Initialize and register all available AI providers."""
    # Register Gemini
    gemini = GeminiProvider()
    ai_provider_registry.register(gemini)

    # Register Grok
    grok = GrokProvider()
    ai_provider_registry.register(grok)

    logger = __import__("logging").getLogger(__name__)
    logger.info(f"Initialized AI providers: {[p.value for p in ai_provider_registry._providers.keys()]}")


def get_active_provider() -> AIProvider:
    """Get the active AI provider based on configuration."""
    provider_type = AIProviderType(settings.AI_PROVIDER.lower())
    provider = ai_provider_registry.get(provider_type)

    if not provider:
        # Fallback to any available provider
        for p in ai_provider_registry._providers.values():
            return p
        raise ValueError(f"No AI providers available")

    return provider


def is_provider_available(provider_type: AIProviderType) -> bool:
    """Check if a provider is configured and available."""
    provider = ai_provider_registry.get(provider_type)
    if not provider:
        return False
    # For providers that don't require API keys, they might always be available
    return True


# Import logging
import logging
logger = logging.getLogger(__name__)

# Initialize providers on module import
initialize_providers()