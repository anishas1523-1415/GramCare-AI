"""OpenAI provider. This is the ONLY file allowed to `import openai`
(requirement #1)."""
from __future__ import annotations
import os

import asyncio
import logging
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

logger = logging.getLogger("gramcare.ai.openai")


class OpenAIProvider(BaseAIProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        # Overridable from the environment because provider model names are
        # retired on the provider's schedule, not ours: gemini-2.0-flash and
        # Groq's llama-3.3-70b-versatile both went dead in place, and each
        # one took every AI feature down with a valid key until a code
        # change shipped. An env var is a dashboard edit instead.
        self._model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        # One client per key, built on first use. A request that rotates
        # through several keys should not rebuild a client each time.
        self._clients: dict[str, object] = {}

    def _client_for(self, api_key: str):
        client = self._clients.get(api_key)
        if client is not None:
            return client
        try:
            import openai  # SDK import isolated to this file

            client = openai.OpenAI(api_key=api_key)
        except Exception as e:  # pragma: no cover
            logger.warning("OpenAI client failed to initialize: %s", e)
            raise ProviderUnavailableError(
                "OpenAI client could not be initialized", provider=self.name, cause=e
            ) from e
        self._clients[api_key] = client
        return client

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY, AITask.MEDICINE_INFO, AITask.PARSE_PRESCRIPTION}

    def supports_vision(self) -> bool:
        # gpt-4o-mini (and gpt-4o) accept image_url content parts.
        return True

    def supports_json(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True

    async def generate(self, request: AIRequest) -> dict:
        if request.image_base64 and self.supports_vision():
            user_content = [
                {"type": "text", "text": request.prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"}},
            ]
        else:
            user_content = request.prompt

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
                        {"role": "user", "content": user_content},
                    ],
                    timeout=request.timeout_seconds,
                )

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_call), timeout=request.timeout_seconds + 2
                )
            except asyncio.TimeoutError as e:
                raise TimeoutError_(
                    f"OpenAI request exceeded {request.timeout_seconds}s", provider=self.name, cause=e
                ) from e
            except Exception as e:
                raise _classify_openai_error(e, self.name) from e

            text = response.choices[0].message.content if response.choices else ""
            return extract_json(text or "", provider=self.name)

        return await self.run_with_rotation(request, _attempt)


def _classify_openai_error(exc: Exception, provider: str) -> AIProviderError:
    """The openai SDK (>=1.x) raises typed exceptions
    (AuthenticationError, RateLimitError, APITimeoutError,
    APIConnectionError, InternalServerError, ...) whose class names line up
    almost 1:1 with our categories — check those first, then fall back to
    the generic text-based classifier."""
    type_name = exc.__class__.__name__

    if type_name == "AuthenticationError":
        return AuthenticationError(str(exc), provider=provider, cause=exc)
    if type_name == "NotFoundError" or is_missing_model(str(exc)):
        return ModelNotFoundError(str(exc), provider=provider, cause=exc)
    if type_name == "RateLimitError":
        # openai's RateLimitError fires for three different things. An account
        # with no credits is not a limit at all and must not be reported as
        # one — see BillingError.
        if is_billing_failure(str(exc)):
            return BillingError(str(exc), provider=provider, cause=exc)
        if "quota" in str(exc).lower():
            return QuotaExceededError(str(exc), provider=provider, cause=exc)
        return RateLimitError(str(exc), provider=provider, cause=exc)
    if type_name in ("APITimeoutError", "Timeout"):
        return TimeoutError_(str(exc), provider=provider, cause=exc)
    if type_name == "APIConnectionError":
        return NetworkError(str(exc), provider=provider, cause=exc)
    if type_name in ("InternalServerError", "APIStatusError"):
        return ProviderUnavailableError(str(exc), provider=provider, cause=exc)

    return classify_exception(exc, provider=provider)
