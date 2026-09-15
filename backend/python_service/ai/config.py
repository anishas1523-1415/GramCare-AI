"""Configuration-driven provider priority (requirement #2).

Nothing in this file hardcodes which provider "wins" — every order below is
a DEFAULT that's only used when the corresponding environment variable is
unset, so operators can reorder providers (or add a new one to the string)
without touching code.

Per-task overrides let the smart-selection behavior from requirement #4
(e.g. "OCR should prefer Gemini/OpenAI, not Groq/Anthropic") live in
configuration rather than in AIManager's selection logic. AIManager's
selection logic ALSO filters by capability (supports_vision, etc.) — the
two mechanisms are complementary: config decides preferred ORDER, capability
checks decide ELIGIBILITY. A misconfigured priority string that lists a
vision-incapable provider first for OCR still can't produce a broken OCR
call, because AIManager skips ineligible providers regardless of position.
"""
from __future__ import annotations

import os

from .base import AITask

# Global fallback order, used for any task without a more specific override.
_DEFAULT_PRIORITY = "gemini,openai,groq,anthropic,mock"

# Per-task defaults, matching the priorities specified for GramCare AI:
#   - AI Triage: Gemini -> OpenAI -> Groq -> Anthropic -> Mock
#   - OCR: only vision-capable providers, Gemini -> OpenAI -> Mock
#   - Doctor Summary: Gemini -> OpenAI -> Groq -> Anthropic
_DEFAULT_PRIORITY_BY_TASK = {
    AITask.TRIAGE: "gemini,openai,groq,anthropic,mock",
    AITask.OCR: "gemini,openai,mock",
    AITask.DOCTOR_SUMMARY: "gemini,openai,groq,anthropic,mock",
    AITask.MEDICINE_INFO: "gemini,openai,groq,anthropic,mock",
    AITask.PARSE_PRESCRIPTION: "gemini,openai,groq,anthropic,mock",
}

#: Env var name -> AITask, for the per-task override variables.
_ENV_VAR_BY_TASK = {
    AITask.TRIAGE: "AI_PROVIDER_PRIORITY_TRIAGE",
    AITask.OCR: "AI_PROVIDER_PRIORITY_OCR",
    AITask.MEDICINE_INFO: "AI_PROVIDER_PRIORITY_MEDICINE_INFO",
    AITask.DOCTOR_SUMMARY: "AI_PROVIDER_PRIORITY_DOCTOR_SUMMARY",
    AITask.PARSE_PRESCRIPTION: "AI_PROVIDER_PRIORITY_PARSE_PRESCRIPTION",
}


def _parse(raw: str) -> list[str]:
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def get_priority(task: AITask) -> list[str]:
    """Ordered list of provider names to try for `task`, e.g.
    ["gemini", "openai", "groq", "anthropic", "mock"].

    Resolution order:
      1. Task-specific env var (AI_PROVIDER_PRIORITY_<TASK>), if set.
      2. Global AI_PROVIDER_PRIORITY env var, if set.
      3. This module's per-task default.
      4. This module's global default.

    "mock" is always appended at the end if the resolved list doesn't
    already include it (requirement #12 — mock must always be reachable as
    a last resort, even if an operator's config string forgets it).
    """
    task_env_var = _ENV_VAR_BY_TASK.get(task)
    raw = None
    if task_env_var:
        raw = os.getenv(task_env_var)
    if not raw:
        raw = os.getenv("AI_PROVIDER_PRIORITY")
    if not raw:
        raw = _DEFAULT_PRIORITY_BY_TASK.get(task, _DEFAULT_PRIORITY)

    order = _parse(raw)
    if "mock" not in order:
        order.append("mock")
    return order


def get_health_cache_seconds() -> float:
    """How long a provider's health/circuit-breaker state is cached before
    re-evaluating (requirement #3). Default 180s (3 minutes), within the
    requested 2-5 minute range."""
    try:
        return float(os.getenv("AI_HEALTH_CACHE_SECONDS", "180"))
    except ValueError:
        return 180.0


def get_request_timeout_seconds() -> float:
    """Per-attempt provider timeout.

    Measured against production (2026-09-15): a warm Gemini triage
    generation takes 11-12s, so the previous 20s left almost no margin —
    a slow instance or a longer answer blew the budget, and because a
    timeout is retryable the request then walked the whole fallback chain
    down to MockProvider and answered "Unknown (AI Engines Unavailable)".
    That is what an AI outage looked like to users even while Gemini was
    healthy.

    30s is ~2.5x the observed generation time, and keeps the worst case
    (2 attempts) at 60s — just inside the mobile clients' own 65s receive
    timeout, so a slow call still returns a real answer instead of the
    client hanging up first.
    """
    try:
        return float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "30"))
    except ValueError:
        return 30.0
