from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum

from app.schemas import BaseSchema


# Type variables for structured output
InputT = TypeVar("InputT", bound=BaseSchema)
OutputT = TypeVar("OutputT", bound=BaseSchema)


class AIModel(str, Enum):
    GEMINI_PRO = "gemini-1.5-pro"
    GEMINI_FLASH = "gemini-1.5-flash"
    GROK = "grok"


class AIProviderType(str, Enum):
    GEMINI = "gemini"
    GROK = "grok"


class AIResponseMetadata(BaseModel):
    model: AIModel
    tokens_input: int
    tokens_output: int
    latency_ms: int
    confidence: float = Field(ge=0.0, le=1.0)
    cost_usd: float = 0.0


class AIResponse(BaseSchema, Generic[OutputT]):
    success: bool
    data: Optional[OutputT] = None
    metadata: AIResponseMetadata
    errors: List[str] = []


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @property
    @abstractmethod
    def provider_type(self) -> AIProviderType:
        pass

    @property
    @abstractmethod
    def default_model(self) -> AIModel:
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[OutputT],
        model: Optional[AIModel] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> AIResponse[OutputT]:
        pass

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        model: Optional[AIModel] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    @abstractmethod
    def estimate_cost(self, model: AIModel, input_tokens: int, output_tokens: int) -> float:
        pass


class AIProviderRegistry:
    """Registry for managing AI providers."""

    def __init__(self):
        self._providers: Dict[AIProviderType, AIProvider] = {}

    def register(self, provider: AIProvider) -> None:
        self._providers[provider.provider_type] = provider

    def get(self, provider_type: AIProviderType) -> Optional[AIProvider]:
        return self._providers.get(provider_type)

    def get_by_model(self, model: AIModel) -> Optional[AIProvider]:
        for provider in self._providers.values():
            if provider.default_model == model:
                return provider
        return None

    async def health_check_all(self) -> Dict[AIProviderType, bool]:
        results = {}
        for provider_type, provider in self._providers.items():
            try:
                results[provider_type] = await provider.health_check()
            except Exception:
                results[provider_type] = False
        return results


# Global registry instance
ai_provider_registry = AIProviderRegistry()


def get_ai_provider(provider_type: AIProviderType) -> AIProvider:
    provider = ai_provider_registry.get(provider_type)
    if not provider:
        raise ValueError(f"AI provider {provider_type} not registered")
    return provider


def get_ai_provider_for_model(model: AIModel) -> AIProvider:
    provider = ai_provider_registry.get_by_model(model)
    if not provider:
        raise ValueError(f"No provider registered for model {model}")
    return provider