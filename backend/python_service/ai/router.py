"""Operational visibility into AIManager (requirements #3 and #8).

Admin-only: this exposes which providers are configured/healthy and
aggregate request/failure/latency counters — useful for verifying the
fallback behavior in requirement #11's checklist, but not something
clinical roles (DOCTOR/HOSPITAL) need, unlike modules/analytics (patient
health data). Deliberately returns no prompts, patient data, or raw
API keys — only provider names, booleans, counts, and latency numbers.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import models
from modules.auth.router import require_role

from .manager import get_ai_manager
from .metrics import ai_metrics

router = APIRouter()


class ProviderHealth(BaseModel):
    provider: str
    configured: bool
    available: bool
    reason: str
    supports_vision: bool
    supports_json: bool
    supports_streaming: bool


@router.get("/health", response_model=list[ProviderHealth])
async def ai_health(current_user: models.User = Depends(require_role("ADMIN"))):
    """Current (cached) health snapshot for every registered provider."""
    manager = get_ai_manager()
    out = []
    for name, provider in manager.all_providers().items():
        status = provider.health_status()
        out.append(
            ProviderHealth(
                provider=name,
                configured=status.configured,
                available=status.available,
                reason=status.reason,
                supports_vision=provider.supports_vision(),
                supports_json=provider.supports_json(),
                supports_streaming=provider.supports_streaming(),
            )
        )
    return out


@router.get("/metrics")
async def ai_metrics_snapshot(current_user: models.User = Depends(require_role("ADMIN"))):
    """requests/failures/average-latency per provider+task, and fallback
    frequency per task, since process start."""
    return ai_metrics.snapshot()
