"""Provider-agnostic contract every AI provider must implement.

Engineering requirement #1 (AIManager is the ONLY AI entry point) is
enforced structurally by this file: `BaseAIProvider.generate()` is the one
method downstream code ever calls, and it returns a plain, already-
normalized dict — never a raw SDK response object. A caller holding a
`BaseAIProvider` has no way to tell which vendor it is talking to.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AITask(str, Enum):
    """Every distinct kind of AI work GramCare AI performs. Adding a new AI
    feature (requirement #10) means adding one value here and one entry in
    each provider's `supported_tasks()` / prompt table — nothing in
    AIManager's selection or fallback logic needs to change."""

    TRIAGE = "triage"
    OCR = "ocr"
    DOCTOR_SUMMARY = "doctor_summary"
    MEDICINE_INFO = "medicine_info"


@dataclass
class HealthStatus:
    """Cached health snapshot for one provider. See BaseAIProvider.is_available
    for why this is cache-based rather than a live test call per request."""

    configured: bool
    available: bool
    reason: str
    checked_at: float = field(default_factory=time.monotonic)


@dataclass
class AIRequest:
    """Everything a provider might need to fulfill a task. Not every field
    is used by every task (e.g. `image_base64` is only set for OCR) —
    providers ignore fields irrelevant to the task they were asked to run."""

    task: AITask
    prompt: str
    image_base64: Optional[str] = None
    timeout_seconds: float = 20.0


class BaseAIProvider(ABC):
    """Abstract base for every AI provider. Concrete providers own their SDK
    import (google-genai / openai / groq / anthropic) — that import must
    NOT appear anywhere outside `ai/providers/*.py` (requirement #1)."""

    #: Short, stable identifier used in config (AI_PROVIDER_PRIORITY=...),
    #: logs, and metrics. Must be unique across providers.
    name: str = "base"

    def __init__(self, api_key: Optional[str], health_cache_seconds: float = 180.0):
        self._api_key = api_key
        self._health_cache_seconds = health_cache_seconds
        self._cached_health: Optional[HealthStatus] = None
        # Timestamp of the last classified failure that implies the
        # provider is currently unhealthy (auth/quota/provider-down). Used
        # to short-circuit is_available() without a live test call.
        self._last_failure_at: Optional[float] = None
        self._last_failure_reason: str = ""

    # ------------------------------------------------------------------
    # Configuration / capability — pure, synchronous, no I/O.
    # ------------------------------------------------------------------
    def is_configured(self) -> bool:
        """True if an API key is present. Does not imply the key is valid —
        that's what is_available()/health_status() are for."""
        return bool(self._api_key)

    @abstractmethod
    def supported_tasks(self) -> set[AITask]:
        """Which AITask values this provider can be selected for at all."""

    @abstractmethod
    def supports_vision(self) -> bool:
        """True if this provider can accept image input for tasks like OCR."""

    @abstractmethod
    def supports_json(self) -> bool:
        """True if this provider can be asked for a strict JSON response
        format (vs. relying on prompt instructions + best-effort parsing)."""

    @abstractmethod
    def supports_streaming(self) -> bool:
        """True if this provider supports token streaming. GramCare AI does
        not currently stream any response to a client, but AIManager's
        selection logic can route streaming-capable tasks here once one
        exists — declared now so adding that feature later needs no
        provider-interface changes."""

    # ------------------------------------------------------------------
    # Health — cached, so we don't burn quota/latency on a live call per
    # request just to ask "are you up?".
    # ------------------------------------------------------------------
    def health_status(self) -> HealthStatus:
        """Returns a cached health snapshot, recomputing only when the cache
        has expired. Deliberately does NOT make a live test call to the
        provider on every miss — that would itself consume quota and add
        latency to the very requests we're trying to protect. Instead,
        "unhealthy" is derived from whether we've seen a disqualifying
        failure (auth/quota/provider-unavailable) recently; a plain
        transient timeout/rate-limit does NOT mark the provider unhealthy,
        since those are exactly the cases we want to retry/fall back on
        without giving up on the provider entirely for the next request.
        """
        now = time.monotonic()
        if self._cached_health is not None and (now - self._cached_health.checked_at) < self._health_cache_seconds:
            return self._cached_health

        if not self.is_configured():
            status = HealthStatus(configured=False, available=False, reason="not_configured")
        elif self._last_failure_at is not None and (now - self._last_failure_at) < self._health_cache_seconds:
            status = HealthStatus(configured=True, available=False, reason=self._last_failure_reason)
        else:
            status = HealthStatus(configured=True, available=True, reason="ok")

        self._cached_health = status
        return status

    def is_available(self) -> bool:
        return self.health_status().available

    def mark_unhealthy(self, reason: str) -> None:
        """Called by AIManager after a disqualifying failure (auth error,
        quota exceeded, or the provider itself reporting unavailable) so
        subsequent requests skip this provider until the health cache
        expires, instead of re-attempting (and re-failing) every single
        request during an outage."""
        self._last_failure_at = time.monotonic()
        self._last_failure_reason = reason
        self._cached_health = None  # force recompute on next health_status()

    def mark_healthy(self) -> None:
        """Called by AIManager after a success, so a provider that recovers
        mid-outage isn't stuck "unhealthy" for the rest of the cache window."""
        self._last_failure_at = None
        self._last_failure_reason = ""
        self._cached_health = None

    # ------------------------------------------------------------------
    # The one real entry point.
    # ------------------------------------------------------------------
    @abstractmethod
    async def generate(self, request: AIRequest) -> dict:
        """Execute `request` and return an already-normalized plain dict
        matching the target schema's field names (requirement #5 — schema
        normalization happens INSIDE the provider). Must raise one of the
        ai.errors.AIProviderError subclasses on any failure; must never let
        a raw SDK exception escape, since AIManager's retry/fallback logic
        keys off these types exclusively.
        """
