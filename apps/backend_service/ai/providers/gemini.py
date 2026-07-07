"""Google Gemini provider. This is the ONLY file in the codebase allowed to
`import google.genai` (requirement #1) — enforced by convention/code review
here, not by a runtime guard, matching how core/ratelimit.py etc. rely on
module boundaries rather than import hooks.
"""
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

logger = logging.getLogger("gramcare.ai.gemini")


class GeminiProvider(BaseAIProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str], model: str = "gemini-2.0-flash", **kwargs):
        super().__init__(api_key, **kwargs)
        self._model = model
        self._client = None
        if api_key:
            try:
                from google import genai  # SDK import isolated to this file

                self._client = genai.Client(api_key=api_key)
            except Exception as e:  # pragma: no cover - import/init failure
                logger.warning("Gemini client failed to initialize: %s", e)
                self._client = None

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY, AITask.MEDICINE_INFO}

    def supports_vision(self) -> bool:
        return True

    def supports_json(self) -> bool:
        # Gemini can be asked for JSON via prompt instructions; the
        # google-genai SDK also supports a response_mime_type config, but we
        # keep parity with the existing prompt-driven approach used
        # elsewhere in this codebase rather than mixing strategies.
        return True

    def supports_streaming(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return bool(self._api_key) and self._client is not None

    async def generate(self, request: AIRequest) -> dict:
        if not self._client:
            raise ProviderUnavailableError("Gemini client not initialized", provider=self.name)

        contents: list = [request.prompt]
        if request.image_base64 and self.supports_vision():
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": request.image_base64}})

        def _call():
            return self._client.models.generate_content(model=self._model, contents=contents)

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call), timeout=request.timeout_seconds
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError_(f"Gemini request exceeded {request.timeout_seconds}s", provider=self.name, cause=e) from e
        except Exception as e:
            raise _classify_gemini_error(e, self.name) from e

        text = getattr(response, "text", None) or ""
        return extract_json(text, provider=self.name)


def _classify_gemini_error(exc: Exception, provider: str) -> AIProviderError:
    """google-genai raises google.genai.errors.APIError subclasses carrying
    an HTTP-like status code; map the common ones explicitly and fall back
    to the generic classifier for anything else."""
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc).lower()

    if status == 401 or "api key not valid" in text or "unauthenticated" in text:
        return AuthenticationError(str(exc), provider=provider, cause=exc)
    if status == 429 or "rate limit" in text:
        return RateLimitError(str(exc), provider=provider, cause=exc)
    if "quota" in text or "resource_exhausted" in text:
        return QuotaExceededError(str(exc), provider=provider, cause=exc)
    if status in (500, 502, 503, 504) or "unavailable" in text:
        return ProviderUnavailableError(str(exc), provider=provider, cause=exc)
    if "network" in text or "connection" in text:
        return NetworkError(str(exc), provider=provider, cause=exc)

    return classify_exception(exc, provider=provider)
