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

    # gemini-2.0-flash was retired by Google — every call returned a 404
    # ("This model ... is no longer available"), which is why every
    # AI-backed feature (triage, OCR, doctor summary, medicine info) was
    # silently falling through to MockProvider's "AI Engines unavailable"
    # response on every single request, for every user, on every app.
    # Confirmed the replacement Google's own error message points to
    # (gemini-3.6-flash) actually works against this same key.
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.6-flash", **kwargs):
        super().__init__(api_key, **kwargs)
        self._model = model
        # One SDK client per key, built on first use and kept. Building a
        # client is cheap but not free, and a request that rotates through
        # several keys would otherwise pay for it repeatedly.
        self._clients: dict[str, object] = {}

    def _client_for(self, api_key: str):
        client = self._clients.get(api_key)
        if client is not None:
            return client
        try:
            from google import genai  # SDK import isolated to this file

            client = genai.Client(api_key=api_key)
        except Exception as e:  # pragma: no cover - import/init failure
            logger.warning("Gemini client failed to initialize: %s", e)
            raise ProviderUnavailableError(
                "Gemini client could not be initialized", provider=self.name, cause=e
            ) from e
        self._clients[api_key] = client
        return client

    def supported_tasks(self) -> set[AITask]:
        return {AITask.TRIAGE, AITask.OCR, AITask.DOCTOR_SUMMARY, AITask.MEDICINE_INFO, AITask.PARSE_PRESCRIPTION}

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

    async def generate(self, request: AIRequest) -> dict:
        contents: list = [request.prompt]
        if request.image_base64 and self.supports_vision():
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": request.image_base64}})

        async def _attempt(api_key: str) -> dict:
            client = self._client_for(api_key)

            def _call():
                return client.models.generate_content(model=self._model, contents=contents)

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_call), timeout=request.timeout_seconds
                )
            except asyncio.TimeoutError as e:
                raise TimeoutError_(
                    f"Gemini request exceeded {request.timeout_seconds}s", provider=self.name, cause=e
                ) from e
            except Exception as e:
                raise _classify_gemini_error(e, self.name) from e

            text = getattr(response, "text", None) or ""
            return extract_json(text, provider=self.name)

        # run_with_rotation moves to the next key on a quota, rate-limit or
        # auth refusal, so one spent free tier no longer takes the whole
        # feature down for the rest of the day.
        return await self.run_with_rotation(request, _attempt)


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
