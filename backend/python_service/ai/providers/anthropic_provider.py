"""Anthropic provider. This is the ONLY file allowed to `import anthropic`
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

logger = logging.getLogger("gramcare.ai.anthropic")


class AnthropicProvider(BaseAIProvider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022", **kwargs):
        super().__init__(api_key, **kwargs)
        self._model = model
        # One client per key, built on first use.
        self._clients: dict[str, object] = {}

    def _client_for(self, api_key: str):
        client = self._clients.get(api_key)
        if client is not None:
            return client
        try:
            import anthropic  # SDK import isolated to this file

            client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:  # pragma: no cover
            logger.warning("Anthropic client failed to initialize: %s", e)
            raise ProviderUnavailableError(
                "Anthropic client could not be initialized", provider=self.name, cause=e
            ) from e
        self._clients[api_key] = client
        return client

    def supported_tasks(self) -> set[AITask]:
        # Included in the TRIAGE and DOCTOR_SUMMARY priority chains per
        # spec. Not part of the default OCR priority (gemini,openai,mock)
        # even though Claude 3+ does support vision — kept out by
        # configuration (ai/config.py), not by supports_vision() below,
        # since it IS technically capable.
        return {AITask.TRIAGE, AITask.DOCTOR_SUMMARY, AITask.OCR, AITask.MEDICINE_INFO, AITask.PARSE_PRESCRIPTION}

    def supports_vision(self) -> bool:
        return True

    def supports_json(self) -> bool:
        # Anthropic has no strict "JSON mode" flag like OpenAI/Groq; JSON
        # compliance here is prompt-instruction-driven only.
        return True

    def supports_streaming(self) -> bool:
        return True

    async def generate(self, request: AIRequest) -> dict:
        content: list = [{"type": "text", "text": request.prompt}]
        if request.image_base64 and self.supports_vision():
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": request.image_base64},
                }
            )

        async def _attempt(api_key: str) -> dict:
            client = self._client_for(api_key)

            def _call():
                return client.messages.create(
                    model=self._model,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": content}],
                )

            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_call), timeout=request.timeout_seconds
                )
            except asyncio.TimeoutError as e:
                raise TimeoutError_(
                    f"Anthropic request exceeded {request.timeout_seconds}s", provider=self.name, cause=e
                ) from e
            except Exception as e:
                raise _classify_anthropic_error(e, self.name) from e

            text = ""
            if response.content:
                # response.content is a list of content blocks; concatenate
                # any text blocks (normally exactly one for our prompts).
                text = "".join(
                    block.text for block in response.content if getattr(block, "type", None) == "text"
                )

            return extract_json(text, provider=self.name)

        return await self.run_with_rotation(request, _attempt)


def _classify_anthropic_error(exc: Exception, provider: str) -> AIProviderError:
    """The anthropic SDK raises typed exceptions
    (AuthenticationError, RateLimitError, APITimeoutError,
    APIConnectionError, InternalServerError, ...) similar to openai's."""
    type_name = exc.__class__.__name__
    text = str(exc).lower()

    if type_name == "AuthenticationError":
        return AuthenticationError(str(exc), provider=provider, cause=exc)
    if type_name == "RateLimitError":
        return RateLimitError(str(exc), provider=provider, cause=exc)
    if "credit balance" in text or "quota" in text:
        return QuotaExceededError(str(exc), provider=provider, cause=exc)
    if type_name in ("APITimeoutError", "Timeout"):
        return TimeoutError_(str(exc), provider=provider, cause=exc)
    if type_name == "APIConnectionError":
        return NetworkError(str(exc), provider=provider, cause=exc)
    if type_name in ("InternalServerError", "APIStatusError", "OverloadedError"):
        return ProviderUnavailableError(str(exc), provider=provider, cause=exc)

    return classify_exception(exc, provider=provider)
