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
    NetworkError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError_,
    classify_exception,
)
from ._util import extract_json

logger = logging.getLogger("gramcare.ai.groq")


class GroqProvider(BaseAIProvider):
    name = "groq"

    def __init__(self, api_key: Optional[str], model: str = "llama-3.3-70b-versatile", **kwargs):
        super().__init__(api_key, **kwargs)
        self._model = model
        self._client = None
        if api_key:
            try:
                from groq import Groq  # SDK import isolated to this file

                self._client = Groq(api_key=api_key)
            except Exception as e:  # pragma: no cover
                logger.warning("Groq client failed to initialize: %s", e)
                self._client = None

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.DOCTOR_SUMMARY}  # deliberately no OCR — see supports_vision()

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

    def is_configured(self) -> bool:
        return bool(self._api_key) and self._client is not None

    async def generate(self, request: AIRequest) -> dict:
        if not self._client:
            raise ProviderUnavailableError("Groq client not initialized", provider=self.name)

        if request.task == AITask.OCR and not self.supports_vision():
            # Should never be reached if AIManager's capability filtering is
            # working correctly — this is a defensive second gate, not the
            # primary enforcement point.
            raise ProviderUnavailableError(
                "Groq provider does not support vision/OCR in current configuration",
                provider=self.name,
            )

        def _call():
            return self._client.chat.completions.create(
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
            raise TimeoutError_(f"Groq request exceeded {request.timeout_seconds}s", provider=self.name, cause=e) from e
        except Exception as e:
            raise _classify_groq_error(e, self.name) from e

        text = response.choices[0].message.content if response.choices else ""
        return extract_json(text or "", provider=self.name)


def _classify_groq_error(exc: Exception, provider: str) -> AIProviderError:
    """Groq's Python SDK mirrors the openai SDK's exception hierarchy
    (it's built on the same httpx-based client generator)."""
    type_name = exc.__class__.__name__
    text = str(exc).lower()

    if type_name == "AuthenticationError" or "invalid api key" in text:
        return AuthenticationError(str(exc), provider=provider, cause=exc)
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
