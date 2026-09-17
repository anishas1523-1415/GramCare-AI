"""Groq provider. This is the ONLY file allowed to `import groq`
(requirement #1)."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from ..base import AIRequest, AITask, BaseAIProvider
from ..errors import (
    AIProviderError,
    AuthenticationError,
    BillingError,
    ModelNotFoundError,
    NetworkError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError_,
    classify_exception,
    is_billing_failure,
    is_missing_model,
)
from ._util import extract_json

logger = logging.getLogger("gramcare.ai.groq")


class GroqProvider(BaseAIProvider):
    name = "groq"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        # Overridable from the environment because provider model names are
        # retired on the provider's schedule, not ours: gemini-2.0-flash and
        # Groq's llama-3.3-70b-versatile both went dead in place, and each
        # one took every AI feature down with a valid key until a code
        # change shipped. An env var is a dashboard edit instead.
        # llama-3.3-70b-versatile now 404s with model_not_found on Groq;
        # gpt-oss-120b is the strongest general model it still serves.
        self._model = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
        # One client per key, built on first use.
        self._clients: dict[str, object] = {}

    def _client_for(self, api_key: str):
        client = self._clients.get(api_key)
        if client is not None:
            return client
        try:
            from groq import Groq  # SDK import isolated to this file

            client = Groq(api_key=api_key)
        except Exception as e:  # pragma: no cover
            logger.warning("Groq client failed to initialize: %s", e)
            raise ProviderUnavailableError(
                "Groq client could not be initialized", provider=self.name, cause=e
            ) from e
        self._clients[api_key] = client
        return client

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.DOCTOR_SUMMARY, AITask.MEDICINE_INFO, AITask.PARSE_PRESCRIPTION}  # deliberately no OCR — see supports_vision()

    def supports_vision(self) -> bool:
        # Most Groq-hosted models (Llama text models) do not accept image
        # input. A small number of vision-capable models exist on Groq, so
        # this is an env override rather than a hardcoded False, per
        # requirement #4 ("do NOT send OCR requests to Groq unless vision
        # support is actually available" — actually available is
        # configurable, not assumed either way).
        return os.getenv("GROQ_SUPPORTS_VISION", "false").strip().lower() == "true"

    def supports_json(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True

    async def generate(self, request: AIRequest) -> dict:
        if request.task == AITask.OCR and not self.supports_vision():
            # Should never be reached if AIManager's capability filtering is
            # working correctly — this is a defensive second gate, not the
            # primary enforcement point.
            raise ProviderUnavailableError(
                "Groq provider does not support vision/OCR in current configuration",
                provider=self.name,
            )

        async def _attempt(api_key: str) -> dict:
            client = self._client_for(api_key)

            def _call():
                return client.chat.completions.create(
                    model=self._model,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": "You return strict JSON matching exactly the format requested in the user prompt. No markdown, no commentary.",
                        },
                        {"role": "user", "content": request.prompt},
                    ],
                    timeout=request.timeout_seconds,
                )

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_call), timeout=request.timeout_seconds + 2
                )
            except asyncio.TimeoutError as e:
                raise TimeoutError_(
                    f"Groq request exceeded {request.timeout_seconds}s", provider=self.name, cause=e
                ) from e
            except Exception as e:
                raise _classify_groq_error(e, self.name) from e

            text = response.choices[0].message.content if response.choices else ""
            return extract_json(text or "", provider=self.name)

        return await self.run_with_rotation(request, _attempt)


def _classify_groq_error(exc: Exception, provider: str) -> AIProviderError:
    """Groq's Python SDK mirrors the openai SDK's exception hierarchy
    (it's built on the same httpx-based client generator)."""
    type_name = exc.__class__.__name__
    text = str(exc).lower()

    if type_name == "AuthenticationError" or "invalid api key" in text:
        return AuthenticationError(str(exc), provider=provider, cause=exc)
    if is_billing_failure(text):
        return BillingError(str(exc), provider=provider, cause=exc)
    if type_name == "NotFoundError" or is_missing_model(text):
        return ModelNotFoundError(str(exc), provider=provider, cause=exc)
    if type_name == "RateLimitError" or "rate limit" in text:
        if "quota" in text:
            return QuotaExceededError(str(exc), provider=provider, cause=exc)
        return RateLimitError(str(exc), provider=provider, cause=exc)
    if type_name in ("APITimeoutError", "Timeout"):
        return TimeoutError_(str(exc), provider=provider, cause=exc)
    if type_name == "APIConnectionError":
        return NetworkError(str(exc), provider=provider, cause=exc)
    if type_name in ("InternalServerError", "APIStatusError"):
        return ProviderUnavailableError(str(exc), provider=provider, cause=exc)

    return classify_exception(exc, provider=provider)
