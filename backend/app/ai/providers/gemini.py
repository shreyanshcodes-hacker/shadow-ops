import json
import logging
from typing import Optional, Type, TypeVar, Dict, Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold

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
)

from app.core.config import settings

logger = logging.getLogger(__name__)

OutputT = TypeVar("OutputT")


class GeminiProvider(AIProvider):
    """Gemini AI provider implementation."""

    def __init__(self):
        self._configured = False
        self._configure()

    def _configure(self):
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._configured = True
                logger.info("Gemini provider configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure Gemini provider: {e}")
                self._configured = False
        else:
            logger.warning("GEMINI_API_KEY not set, Gemini provider unavailable")

    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.GEMINI

    @property
    def default_model(self) -> AIModel:
        model_str = settings.GEMINI_MODEL
        if "pro" in model_str.lower():
            return AIModel.GEMINI_PRO
        return AIModel.GEMINI_FLASH

    def _get_model_instance(self, model: Optional[AIModel] = None):
        if not self._configured:
            raise AIProviderAuthError("Gemini API key not configured")

        model_name = model.value if model else self.default_model.value
        return genai.GenerativeModel(model_name)

    def _build_generation_config(
        self,
        temperature: float,
        max_tokens: Optional[int],
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> GenerationConfig:
        config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens or settings.AI_MAX_OUTPUT_TOKENS,
            response_mime_type="application/json" if response_schema else "text/plain",
        )
        if response_schema:
            config.response_schema = response_schema
        return config

    def _handle_gemini_error(self, error: Exception) -> AIProviderError:
        error_str = str(error).lower()
        if "api key" in error_str or "authentication" in error_str or "permission" in error_str:
            return AIProviderAuthError(f"Gemini authentication failed: {error}")
        elif "rate limit" in error_str or "quota" in error_str or "429" in error_str:
            return AIProviderRateLimitError(f"Gemini rate limit exceeded: {error}")
        elif "timeout" in error_str or "deadline" in error_str:
            return AIProviderTimeoutError(f"Gemini request timed out: {error}")
        elif "500" in error_str or "503" in error_str or "internal" in error_str:
            return AIProviderServerError(f"Gemini server error: {error}")
        else:
            return AIProviderError(f"Gemini error: {error}")

    async def generate_structured(
        self,
        prompt: str,
        output_schema: Type[OutputT],
        model: Optional[AIModel] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> AIResponse[OutputT]:
        if not self._configured:
            return AIResponse(
                success=False,
                data=None,
                metadata=AIResponseMetadata(
                    model=model or self.default_model,
                    tokens_input=0,
                    tokens_output=0,
                    latency_ms=0,
                    confidence=0.0,
                    cost_usd=0.0,
                ),
                errors=["Gemini provider not configured"],
            )

        try:
            model_instance = self._get_model_instance(model)

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            schema_dict = output_schema.model_json_schema()

            generation_config = self._build_generation_config(
                temperature=temperature,
                max_tokens=max_tokens,
                response_schema=schema_dict,
            )

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }

            result, latency_ms = await self._execute_with_timing(
                model_instance.generate_content_async(
                    full_prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
            )

            if not result.candidates:
                return AIResponse(
                    success=False,
                    data=None,
                    metadata=AIResponseMetadata(
                        model=model or self.default_model,
                        tokens_input=0,
                        tokens_output=0,
                        latency_ms=latency_ms,
                        confidence=0.0,
                        cost_usd=0.0,
                    ),
                    errors=["No candidates returned from Gemini"],
                )

            candidate = result.candidates[0]
            if candidate.finish_reason != 1:
                return AIResponse(
                    success=False,
                    data=None,
                    metadata=AIResponseMetadata(
                        model=model or self.default_model,
                        tokens_input=0,
                        tokens_output=0,
                        latency_ms=latency_ms,
                        confidence=0.0,
                        cost_usd=0.0,
                    ),
                    errors=[f"Generation stopped: {candidate.finish_reason}"],
                )

            try:
                parsed_data = json.loads(result.text)
                validated_data = output_schema(**parsed_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini JSON response: {e}")
                return AIResponse(
                    success=False,
                    data=None,
                    metadata=AIResponseMetadata(
                        model=model or self.default_model,
                        tokens_input=0,
                        tokens_output=0,
                        latency_ms=latency_ms,
                        confidence=0.0,
                        cost_usd=0.0,
                    ),
                    errors=[f"Invalid JSON response: {e}"],
                )
            except Exception as e:
                logger.error(f"Failed to validate Gemini response against schema: {e}")
                return AIResponse(
                    success=False,
                    data=None,
                    metadata=AIResponseMetadata(
                        model=model or self.default_model,
                        tokens_input=0,
                        tokens_output=0,
                        latency_ms=latency_ms,
                        confidence=0.0,
                        cost_usd=0.0,
                    ),
                    errors=[f"Schema validation failed: {e}"],
                )

            tokens_input = result.usage_metadata.prompt_token_count if result.usage_metadata else 0
            tokens_output = result.usage_metadata.candidates_token_count if result.usage_metadata else 0

            return AIResponse(
                success=True,
                data=validated_data,
                metadata=AIResponseMetadata(
                    model=model or self.default_model,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    latency_ms=latency_ms,
                    confidence=0.8,
                    cost_usd=self.estimate_cost(model or self.default_model, tokens_input, tokens_output),
                ),
                errors=[],
            )

        except AIProviderError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in Gemini generate_structured: {e}")
            raise self._handle_gemini_error(e)

    async def generate_text(
        self,
        prompt: str,
        model: Optional[AIModel] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not self._configured:
            raise AIProviderAuthError("Gemini provider not configured")

        try:
            model_instance = self._get_model_instance(model)

            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens or settings.AI_MAX_OUTPUT_TOKENS,
            )

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }

            result, _ = await self._execute_with_timing(
                model_instance.generate_content_async(
                    full_prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
            )

            if not result.candidates or not result.text:
                raise AIProviderError("No text generated by Gemini")

            return result.text

        except AIProviderError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in Gemini generate_text: {e}")
            raise self._handle_gemini_error(e)

    async def health_check(self) -> bool:
        if not self._configured:
            return False

        try:
            model_instance = self._get_model_instance()
            result = await model_instance.generate_content_async(
                "Health check",
                generation_config=GenerationConfig(max_output_tokens=10),
            )
            return bool(result.candidates and result.text)
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False

    def estimate_cost(self, model: AIModel, input_tokens: int, output_tokens: int) -> float:
        pricing = {
            AIModel.GEMINI_PRO: {"input": 3.50 / 1_000_000, "output": 10.50 / 1_000_000},
            AIModel.GEMINI_FLASH: {"input": 0.075 / 1_000_000, "output": 0.30 / 1_000_000},
        }
        rates = pricing.get(model, pricing[AIModel.GEMINI_FLASH])
        return (input_tokens * rates["input"]) + (output_tokens * rates["output"])