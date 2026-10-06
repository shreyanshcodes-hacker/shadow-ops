import json
import logging
from typing import Optional, Type, TypeVar

import httpx

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


class GrokProvider(AIProvider):
    """Grok (xAI) AI provider implementation."""

    def __init__(self):
        self._configured = False
        self._client: Optional[httpx.AsyncClient] = None
        self._configure()

    def _configure(self):
        if settings.GROK_API_KEY:
            self._configured = True
            logger.info("Grok provider configured successfully")
        else:
            logger.warning("GROK_API_KEY not set, Grok provider unavailable")

    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.GROK

    @property
    def default_model(self) -> AIModel:
        return AIModel.GROK

    def _get_client(self) -> httpx.AsyncClient:
        if not self._configured:
            raise AIProviderAuthError("Grok API key not configured")

        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url="https://api.x.ai/v1",
                headers={
                    "Authorization": f"Bearer {settings.GROK_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=settings.AI_TIMEOUT_SECONDS,
            )
        return self._client

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _handle_grok_error(self, error: Exception, status_code: Optional[int] = None) -> AIProviderError:
        error_str = str(error).lower()
        if status_code == 401 or "unauthorized" in error_str or "authentication" in error_str:
            return AIProviderAuthError(f"Grok authentication failed: {error}")
        elif status_code == 429 or "rate limit" in error_str:
            return AIProviderRateLimitError(f"Grok rate limit exceeded: {error}")
        elif status_code and status_code >= 500:
            return AIProviderServerError(f"Grok server error: {error}")
        elif "timeout" in error_str:
            return AIProviderTimeoutError(f"Grok request timed out: {error}")
        else:
            return AIProviderError(f"Grok error: {error}")

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
                errors=["Grok provider not configured"],
            )

        import time
        start = time.time()

        try:
            client = self._get_client()

            schema = output_schema.model_json_schema()
            schema_str = json.dumps(schema, separators=(",", ":"))

            full_prompt = f"{prompt}\n\nYou must respond with valid JSON matching this schema:\n{schema_str}"

            payload = {
                "model": settings.GROK_MODEL,
                "messages": self._build_messages(full_prompt, system_prompt),
                "temperature": temperature,
                "max_tokens": max_tokens or settings.AI_MAX_OUTPUT_TOKENS,
                "response_format": {"type": "json_object"},
            }

            response = await client.post("/chat/completions", json=payload)
            latency_ms = int((time.time() - start) * 1000)

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                raise self._handle_grok_error(Exception(error_msg), response.status_code)

            data = response.json()

            if not data.get("choices"):
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
                    errors=["No choices returned from Grok"],
                )

            content = data["choices"][0]["message"]["content"]

            try:
                parsed_data = json.loads(content)
                validated_data = output_schema(**parsed_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Grok JSON response: {e}")
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
                logger.error(f"Failed to validate Grok response against schema: {e}")
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

            usage = data.get("usage", {})
            tokens_input = usage.get("prompt_tokens", 0)
            tokens_output = usage.get("completion_tokens", 0)

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
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Grok request timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise self._handle_grok_error(e, e.response.status_code)
        except Exception as e:
            logger.exception(f"Unexpected error in Grok generate_structured: {e}")
            raise AIProviderError(f"Grok error: {e}")

    async def generate_text(
        self,
        prompt: str,
        model: Optional[AIModel] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not self._configured:
            raise AIProviderAuthError("Grok provider not configured")

        try:
            client = self._get_client()

            payload = {
                "model": settings.GROK_MODEL,
                "messages": self._build_messages(prompt, system_prompt),
                "temperature": temperature,
                "max_tokens": max_tokens or settings.AI_MAX_OUTPUT_TOKENS,
            }

            response = await client.post("/chat/completions", json=payload)

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                raise self._handle_grok_error(Exception(error_msg), response.status_code)

            data = response.json()

            if not data.get("choices") or not data["choices"][0]["message"].get("content"):
                raise AIProviderError("No text generated by Grok")

            return data["choices"][0]["message"]["content"]

        except AIProviderError:
            raise
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Grok request timed out: {e}")
        except httpx.HTTPStatusError as e:
            raise self._handle_grok_error(e, e.response.status_code)
        except Exception as e:
            logger.exception(f"Unexpected error in Grok generate_text: {e}")
            raise AIProviderError(f"Grok error: {e}")

    async def health_check(self) -> bool:
        if not self._configured:
            return False

        try:
            client = self._get_client()
            response = await client.post(
                "/chat/completions",
                json={
                    "model": settings.GROK_MODEL,
                    "messages": [{"role": "user", "content": "Health check"}],
                    "max_tokens": 10,
                },
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Grok health check failed: {e}")
            return False

    def estimate_cost(self, model: AIModel, input_tokens: int, output_tokens: int) -> float:
        pricing = {
            AIModel.GROK: {"input": 5.00 / 1_000_000, "output": 15.00 / 1_000_000},
        }
        rates = pricing.get(model, pricing[AIModel.GROK])
        return (input_tokens * rates["input"]) + (output_tokens * rates["output"])

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()