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
from .keypool import KeyPool
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

#: Plural counterparts, holding a comma-separated list. Several free keys
#: for the same provider multiply the daily cap, which is the difference
#: between the assistant working all day and working once.
_ENV_KEYS_BY_PROVIDER = {
    "gemini": "GEMINI_API_KEYS",
    "openai": "OPENAI_API_KEYS",
    "groq": "GROQ_API_KEYS",
    "anthropic": "ANTHROPIC_API_KEYS",
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
    #: True when the answer came from MockProvider *because* every real
    #: provider was out of quota or rate limited, rather than because none
    #: is configured or one is broken. The apps show a "limit reached — do
    #: you have your own key?" prompt on this and nothing else, so a
    #: misconfigured server never asks the user to fix it with a key.
    quota_exhausted: bool = False

    #: True whenever the answer is a MockProvider fallback and the caller
    #: did not already supply a key. Quota is only one of the reasons a real
    #: provider drops out — a revoked, mistyped or entirely absent key looks
    #: nothing like quota exhaustion, and gating the prompt on quota alone
    #: meant the commonest failures showed "AI engines unavailable" with no
    #: way forward. A user's own key fixes all of them, so all of them get
    #: offered the box.
    user_key_may_help: bool = False

    #: Why the caller's own key failed, when they supplied one: the error
    #: category (AuthenticationError, QuotaExceededError, ...). Lets the apps
    #: say "that key was rejected" instead of silently showing the fallback,
    #: which read as the AI being broken even after someone pasted a key.
    user_key_error: Optional[str] = None

    #: provider -> error category, for every real provider that failed on
    #: this request. Diagnostics only; never contains key material.
    failures: dict = field(default_factory=dict)


def provider_for_user_key(key: Optional[str]) -> Optional[str]:
    """Which provider issued `key`, from its prefix.

    A user's key must only ever be sent to the company that issued it. The
    manager used to pass it to every provider in turn, so a Google key
    pasted into the app went to OpenAI's and Groq's servers too, handing a
    credential to third parties and guaranteeing two auth failures on every
    request. Order matters: "sk-ant-" before the generic "sk-". AI Studio
    issues both the older "AIza" keys and the newer "AQ." ones.
    """
    if not key:
        return None
    k = key.strip()
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k.startswith("gsk_"):
        return "groq"
    if k.startswith("sk-"):
        return "openai"
    if k.startswith("AIza") or k.startswith("AQ."):
        return "gemini"
    return None


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
                plural_var = _ENV_KEYS_BY_PROVIDER.get(name)
                pool = (
                    KeyPool.from_env(name, plural_var, env_var)
                    if env_var and plural_var
                    else None
                )
                self._providers[name] = cls(
                    api_key=None if pool else (os.getenv(env_var) if env_var else None),
                    health_cache_seconds=health_cache,
                    key_pool=pool,
                )

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
        user_api_key: Optional[str] = None,
    ) -> AIOutcome:
        request_id = uuid.uuid4().hex[:12]
        candidates = self._candidates_for(task, requires_vision=image_base64 is not None)
        attempted: list[str] = []
        total_retries = 0
        overall_start = time.monotonic()

        # The user's key goes only to the provider that issued it, and that
        # provider goes first: someone who pasted a key is asking to use it.
        user_api_key = (user_api_key or "").strip() or None
        key_owner = provider_for_user_key(user_api_key) if user_api_key else None
        if user_api_key and key_owner is None:
            # Unrecognised format. The app tells people to get a key from
            # Google AI Studio, so Gemini is the only reasonable owner, and
            # still the only provider it is sent to.
            key_owner = "gemini"
        if key_owner:
            candidates = sorted(candidates, key=lambda p: 0 if p.name == key_owner else 1)

        # quota_blocked: some real provider was refused for quota or a rate
        # limit. other_failure: some real provider failed for any other
        # reason (down, timed out, model retired, account unfunded, bad
        # response). "AI limit reached" is only true when quota is the whole
        # story; otherwise an unfunded OpenAI account or a retired Groq
        # model told users they had hit a limit they had not.
        quota_blocked = False
        other_failure = False
        saw_real_provider = False
        failures: dict[str, str] = {}
        user_key_error: Optional[str] = None

        for provider in candidates:
            key_here = user_api_key if provider.name == key_owner else None
            if provider.name != "mock":
                saw_real_provider = True
                if provider.quota_exhausted() and not key_here:
                    quota_blocked = True
            # The circuit breaker describes the server's own keys; it must not
            # stop a user's key from being tried.
            if not provider.is_available() and provider.name != "mock" and not key_here:
                logger.info(
                    "ai_request request_id=%s task=%s provider=%s skipped reason=unhealthy",
                    request_id, task.value, provider.name,
                )
                continue

            attempted.append(provider.name)
            outcome = await self._call_with_retry(
                provider, task, prompt, image_base64, timeout_seconds, request_id,
                user_api_key=key_here,
            )
            total_retries += outcome["retries"]
            error = outcome.get("error")
            if error is not None and provider.name != "mock":
                failures[provider.name] = error.category
                if key_here:
                    user_key_error = error.category
                elif error.category in ("QuotaExceededError", "RateLimitError"):
                    quota_blocked = True
                else:
                    other_failure = True
            elif not outcome["success"] and provider.name != "mock":
                failures[provider.name] = "Unclassified"
                other_failure = True

            if outcome["success"]:
                total_latency_ms = round((time.monotonic() - overall_start) * 1000, 1)
                fallback_occurred = len(attempted) > 1
                if fallback_occurred:
                    ai_metrics.record_fallback(task.value)
                logger.info(
                    "ai_request request_id=%s task=%s provider_selected=%s provider_used=%s "
                    "latency_ms=%s retry_count=%s fallback=%s failures=%s",
                    request_id, task.value, candidates[0].name, provider.name,
                    total_latency_ms, total_retries, fallback_occurred, failures,
                )
                used_mock = provider.name == "mock"
                return AIOutcome(
                    data=outcome["data"],
                    provider_used=provider.name,
                    request_id=request_id,
                    latency_ms=total_latency_ms,
                    retry_count=total_retries,
                    attempted_providers=attempted,
                    fallback_occurred=fallback_occurred,
                    used_mock=used_mock,
                    quota_exhausted=(used_mock and quota_blocked and not other_failure and saw_real_provider),
                    user_key_may_help=(used_mock and not user_api_key),
                    user_key_error=user_key_error if used_mock else None,
                    failures=failures,
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
        user_api_key: Optional[str] = None,
    ) -> dict:
        request = AIRequest(
            task=task,
            prompt=prompt,
            image_base64=image_base64,
            timeout_seconds=timeout_seconds or self._default_timeout,
            user_api_key=user_api_key,
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
                # Only the server's own keys may open the breaker. A user's
                # mistyped or spent key used to mark the provider unhealthy
                # for the whole health-cache window, so one person pasting a
                # bad key took Gemini away from every other user for minutes.
                if not user_api_key and e.category in (
                    "AuthenticationError", "QuotaExceededError", "BillingError",
                    "ProviderUnavailableError", "ModelNotFoundError",
                ):
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
