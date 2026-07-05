"""GramCare AI's unified AI layer.

Import surface for the rest of the backend:

    from ai import get_ai_manager, AITask

    outcome = await get_ai_manager().run(AITask.TRIAGE, prompt=prompt)
    data = outcome.data

No other package may import google-genai / openai / groq / anthropic
directly — see ai/providers/*.py, each of which owns exactly one SDK.
"""
from .base import AIRequest, AITask, HealthStatus
from .errors import (
    AIProviderError,
    AuthenticationError,
    InvalidResponseError,
    JSONParseError,
    NetworkError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    TimeoutError_,
)
from .manager import AIManager, AIOutcome, AllProvidersFailedError, get_ai_manager

__all__ = [
    "AIManager",
    "AIOutcome",
    "AIRequest",
    "AITask",
    "AllProvidersFailedError",
    "HealthStatus",
    "get_ai_manager",
    "AIProviderError",
    "AuthenticationError",
    "InvalidResponseError",
    "JSONParseError",
    "NetworkError",
    "ProviderUnavailableError",
    "QuotaExceededError",
    "RateLimitError",
    "TimeoutError_",
]
