"""AIManager — the ONLY entry point for AI calls anywhere in GramCare AI
(requirement #1).

No other module may import google-genai / openai / groq / anthropic, or
hold a reference to a provider's raw SDK client. Every AI-backed feature
(triage, OCR, doctor summary, and any future one) goes through
`ai_manager.run(task, ...)`, which:

  1. Resolves the candidate provider order from configuration (ai/config.py),
     filtered to providers that both declare support for `task` and, for
     vision tasks, report supports_vision() (requirement #4).
  2. Skips any candidate whose cached health check says it's currently
     unavailable (requirement #3) — no live "ping" call, see base.py.
  3. Calls the provider, applying the error-type-driven retry policy from
     ai/errors.py (requirement #6).
  4. Logs provider selected/used, latency, retry count, and fallback reason
     for every request — never the prompt or patient data (requirement #7).
  5. Records metrics for every attempt (requirement #8).
  6. Always eventually reaches MockProvider if every real provider fails
     (requirement #12) — the application never raises just because AI is
     down.

Downstream callers get back a plain dict (already schema-shaped by the
provider — requirement #5) plus metadata; AIManager deliberately does not
import any Pydantic response model from `modules/*`, so this package has no
dependency on the routers that use it (they depend on it, not the other
way around).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .base import AIRequest, AITask, BaseAIProvider
from .config import get_health_cache_seconds, get_priority, get_request_timeout_seconds
from .errors import AIProviderError
from .metrics import ai_metrics
from .providers import PROVIDER_CLASSES

logger = logging.getLogger("gramcare.ai.manager")

#: Env var name each provider's API key is read from (requirement #9 — never
#: hardcoded; "mock" needs none).
_ENV_KEY_BY_PROVIDER = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "mock": None,
}


@dataclass
class AIOutcome:
    data: dict
    provider_used: str
    request_id: str
    latency_ms: float
    retry_count: int
    attempted_providers: list = field(default_factory=list)
    fallback_occurred: bool = False
    used_mock: bool = False


class AllProvidersFailedError(RuntimeError):
    """Raised only if even MockProvider fails — should never happen in
    practice (MockProvider has no external dependency to fail on), but
    callers must not silently get `None` if it somehow does."""


class AIManager:
    def __init__(self, providers: Optional[dict[str, BaseAIProvider]] = None):
        if providers is not None:
            # Dependency injection path — used by tests to substitute fakes
            # without monkeypatching module globals.
            self._providers = providers
        else:
            health_cache = get_health_cache_seconds()
            self._providers = {}
            for name, cls in PROVIDER_CLASSES.items():
                env_var = _ENV_KEY_BY_PROVIDER.get(name)
                api_key = os.getenv(env_var) if env_var else None
                self._providers[name] = cls(api_key=api_key, health_cache_seconds=health_cache)

        self._default_timeout = get_request_timeout_seconds()

    def provider(self, name: str) -> Optional[BaseAIProvider]:
        return self._providers.get(name)

    def all_providers(self) -> dict[str, BaseAIProvider]:
        return dict(self._providers)

    def _candidates_for(self, task: AITask, requires_vision: bool = False) -> list[BaseAIProvider]:
        order = get_priority(task)
        candidates = []
        # OCR always carries an image, so it's always vision-gated regardless
        # of the caller; other tasks (e.g. TRIAGE with an optional symptom
        # photo — planning doc: "இமேஜும் ஆட் பண்ணலாம்") are only vision-gated
        # when this specific call actually attaches an image.
        needs_vision = requires_vision or task == AITask.OCR
        for name in order:
            p = self._providers.get(name)
            if p is None:
                logger.warning("Configured provider '%s' is not registered — skipping.", name)
                continue
            if task not in p.supported_tasks():
                continue
            if needs_vision and not p.supports_vision():
                # Requirement #4, made explicit rather than relying solely
                # on supported_tasks(): never route an image-bearing request
                # to a provider without vision support, regardless of what
                # configuration says.
                continue
            candidates.append(p)
        return candidates

    async def run(
        self,
        task: AITask,
        *,
        prompt: str,
        image_base64: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> AIOutcome:
        request_id = uuid.uuid4().hex[:12]
        candidates = self._candidates_for(task, requires_vision=image_base64 is not None)
        attempted: list[str] = []
        total_retries = 0
        overall_start = time.monotonic()

        for provider in candidates:
            if not provider.is_available() and provider.name != "mock":
                logger.info(
                    "ai_request request_id=%s task=%s provider=%s skipped reason=unhealthy",
                    request_id, task.value, provider.name,
                )
                continue

            attempted.append(provider.name)
            outcome = await self._call_with_retry(provider, task, prompt, image_base64, timeout_seconds, request_id)
            total_retries += outcome["retries"]

            if outcome["success"]:
                total_latency_ms = round((time.monotonic() - overall_start) * 1000, 1)
                fallback_occurred = len(attempted) > 1
                if fallback_occurred:
                    ai_metrics.record_fallback(task.value)
                logger.info(
                    "ai_request request_id=%s task=%s provider_selected=%s provider_used=%s "
                    "latency_ms=%s retry_count=%s fallback=%s",
                    request_id, task.value, candidates[0].name, provider.name,
                    total_latency_ms, total_retries, fallback_occurred,
                )
                return AIOutcome(
                    data=outcome["data"],
                    provider_used=provider.name,
                    request_id=request_id,
                    latency_ms=total_latency_ms,
                    retry_count=total_retries,
                    attempted_providers=attempted,
                    fallback_occurred=fallback_occurred,
                    used_mock=(provider.name == "mock"),
                )
            # else: fall through to the next candidate.

        # Every configured/eligible candidate failed. This should be
        # unreachable in practice because get_priority() always appends
        # "mock" and MockProvider.generate() cannot fail — but if the mock
        # provider was somehow removed from the registry, fail loudly rather
        # than returning None to a caller expecting a dict.
        raise AllProvidersFailedError(
            f"All AI providers failed for task={task.value}, request_id={request_id}, attempted={attempted}"
        )

    async def _call_with_retry(
        self,
        provider: BaseAIProvider,
        task: AITask,
        prompt: str,
        image_base64: Optional[str],
        timeout_seconds: Optional[float],
        request_id: str,
    ) -> dict:
        request = AIRequest(
            task=task,
            prompt=prompt,
            image_base64=image_base64,
            timeout_seconds=timeout_seconds or self._default_timeout,
        )

        retries = 0
        max_attempts = 2  # 1 initial attempt + 1 retry, only for retryable error types
        last_error: Optional[AIProviderError] = None

        for attempt in range(max_attempts):
            start = time.monotonic()
            try:
                data = await provider.generate(request)
                latency_ms = round((time.monotonic() - start) * 1000, 1)
                ai_metrics.record_success(provider.name, task.value, latency_ms)
                provider.mark_healthy()
                return {"success": True, "data": data, "retries": retries}
            except AIProviderError as e:
                latency_ms = round((time.monotonic() - start) * 1000, 1)
                ai_metrics.record_failure(provider.name, task.value, e.category, latency_ms)
                last_error = e

                logger.warning(
                    "ai_request request_id=%s task=%s provider=%s failed category=%s retryable=%s attempt=%s",
                    request_id, task.value, provider.name, e.category, e.retryable, attempt + 1,
                )

                # Circuit-breaker: disqualifying failures mark the provider
                # unhealthy so subsequent requests (not just this one) skip
                # it until the health cache expires.
                if e.category in ("AuthenticationError", "QuotaExceededError", "ProviderUnavailableError"):
                    provider.mark_unhealthy(reason=e.category)

                if e.retryable and attempt < max_attempts - 1:
                    retries += 1
                    await asyncio.sleep(0.5 * (attempt + 1))  # small linear backoff
                    continue
                break
            except Exception as e:  # pragma: no cover - defensive: a provider
                # forgot to classify an exception. Treat as a hard failure
                # for this provider rather than letting it crash the request.
                latency_ms = round((time.monotonic() - start) * 1000, 1)
                logger.error(
                    "ai_request request_id=%s task=%s provider=%s raised an unclassified exception: %s",
                    request_id, task.value, provider.name, e.__class__.__name__,
                )
                ai_metrics.record_failure(provider.name, task.value, "Unclassified", latency_ms)
                last_error = None
                break

        return {"success": False, "data": None, "retries": retries, "error": last_error}


# Process-wide singleton, constructed lazily so importing this module never
# has side effects (e.g. during test collection) until AI is actually used.
_instance: Optional[AIManager] = None


def get_ai_manager() -> AIManager:
    global _instance
    if _instance is None:
        _instance = AIManager()
    return _instance
