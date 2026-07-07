"""OpenAI provider. This is the ONLY file allowed to `import openai`
(requirement #1)."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..base import AIRequest, AITask, BaseAIProvider
from ..errors import (
    AIProviderError,
    AuthenticationError,
    NetworkError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError_,
    classify_exception,
)
from ._util import extract_json

logger = logging.getLogger("gramcare.ai.openai")


class OpenAIProvider(BaseAIProvider):
    name = "openai"

    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini", **kwargs):
        super().__init__(api_key, **kwargs)
        self._model = model
        self._client = None
        if api_key:
            try:
                import openai  # SDK import isolated to this file

                self._client = openai.OpenAI(api_key=api_key)
            except Exception as e:  # pragma: no cover
                logger.warning("OpenAI client failed to initialize: %s", e)
                self._client = None

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY, AITask.MEDICINE_INFO}

    def supports_vision(self) -> bool:
        # gpt-4o-mini (and gpt-4o) accept image_url content parts.
        return True

    def supports_json(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key) and self._client is not None

    async def generate(self, request: AIRequest) -> dict:
        if not self._client:
            raise ProviderUnavailableError("OpenAI client not initialized", provider=self.name)

        if request.image_base64 and self.supports_vision():
            user_content = [
                {"type": "text", "text": request.prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"}},
            ]
        else:
            user_content = request.prompt

        def _call():
            return self._client.chat.completions.create(
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
            raise TimeoutError_(f"OpenAI request exceeded {request.timeout_seconds}s", provider=self.name, cause=e) from e
        except Exception as e:
            raise _classify_openai_error(e, self.name) from e

        text = response.choices[0].message.content if response.choices else ""
        return extract_json(text or "", provider=self.name)


def _classify_openai_error(exc: Exception, provider: str) -> AIProviderError:
    """The openai SDK (>=1.x) raises typed exceptions
    (AuthenticationError, RateLimitError, APITimeoutError,
    APIConnectionError, InternalServerError, ...) whose class names line up
    almost 1:1 with our categories — check those first, then fall back to
    the generic text-based classifier."""
    type_name = exc.__class__.__name__

    if type_name == "AuthenticationError":
        return AuthenticationError(str(exc), provider=provider, cause=exc)
    if type_name == "RateLimitError":
        # openai's RateLimitError also fires for quota exhaustion; disambiguate by message.
        if "quota" in str(exc).lower() or "insufficient_quota" in str(exc).lower():
            return QuotaExceededError(str(exc), provider=provider, cause=exc)
        return RateLimitError(str(exc), provider=provider, cause=exc)
    if type_name in ("APITimeoutError", "Timeout"):
        return TimeoutError_(str(exc), provider=provider, cause=exc)
    if type_name == "APIConnectionError":
        return NetworkError(str(exc), provider=provider, cause=exc)
    if type_name in ("InternalServerError", "APIStatusError"):
        return ProviderUnavailableError(str(exc), provider=provider, cause=exc)

    return classify_exception(exc, provider=provider)
