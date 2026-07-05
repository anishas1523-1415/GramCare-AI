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
}

#: Env var name -> AITask, for the per-task override variables.
_ENV_VAR_BY_TASK = {
    AITask.TRIAGE: "AI_PROVIDER_PRIORITY_TRIAGE",
    AITask.OCR: "AI_PROVIDER_PRIORITY_OCR",
    AITask.DOCTOR_SUMMARY: "AI_PROVIDER_PRIORITY_DOCTOR_SUMMARY",
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
    try:
        return float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "20"))
    except ValueError:
        return 20.0
