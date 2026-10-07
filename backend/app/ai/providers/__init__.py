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

# Lazy imports for provider classes to avoid config dependency at import time
_GeminiProvider = None
_GrokProvider = None

def _get_gemini_provider():
    global _GeminiProvider
    if _GeminiProvider is None:
        from app.ai.providers.gemini import GeminiProvider
        _GeminiProvider = GeminiProvider
    return _GeminiProvider

def _get_grok_provider():
    global _GrokProvider
    if _GrokProvider is None:
        from app.ai.providers.grok import GrokProvider
        _GrokProvider = GrokProvider
    return _GrokProvider


def initialize_providers():
    """Initialize and register all available AI providers."""
    # Register Gemini
    try:
        gemini = _get_gemini_provider()()
        ai_provider_registry.register(gemini)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to initialize Gemini provider: {e}")

    # Register Grok
    try:
        grok = _get_grok_provider()()
        ai_provider_registry.register(grok)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to initialize Grok provider: {e}")

    logger = __import__("logging").getLogger(__name__)
    logger.info(f"Initialized AI providers: {[p.value for p in ai_provider_registry._providers.keys()]}")


def get_active_provider() -> AIProvider:
    """Get the active AI provider based on configuration."""
    from app.core.config import settings
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

# Do NOT initialize providers on module import - do it lazily when needed
_providers_initialized = False

def _ensure_providers_initialized():
    global _providers_initialized
    if not _providers_initialized:
        initialize_providers()
        _providers_initialized = True

# Patch get_ai_provider and get_ai_provider_for_model to ensure initialization
_original_get_ai_provider = get_ai_provider
def get_ai_provider(provider_type: AIProviderType) -> AIProvider:
    _ensure_providers_initialized()
    return _original_get_ai_provider(provider_type)

_original_get_ai_provider_for_model = get_ai_provider_for_model
def get_ai_provider_for_model(model: AIModel) -> AIProvider:
    _ensure_providers_initialized()
    return _original_get_ai_provider_for_model(model)

# Also patch the registry methods
_original_registry_get = ai_provider_registry.get
def _registry_get_patched(self, provider_type: AIProviderType):
    _ensure_providers_initialized()
    return _original_registry_get(provider_type)
ai_provider_registry.get = _registry_get_patched.__get__(ai_provider_registry, AIProviderRegistry)

_original_registry_get_by_model = ai_provider_registry.get_by_model
def _registry_get_by_model_patched(self, model: AIModel):
    _ensure_providers_initialized()
    return _original_registry_get_by_model(model)
ai_provider_registry.get_by_model = _registry_get_by_model_patched.__get__(ai_provider_registry, AIProviderRegistry)
