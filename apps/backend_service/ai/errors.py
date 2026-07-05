"""Error classification for AI provider calls.

Every provider implementation is required to translate whatever its SDK
raises into one of these types before it escapes `generate()`. AIManager
decides retry/fallback behavior purely by exception TYPE — it never
inspects provider-specific exception classes or message strings — which is
what lets `manager.py` stay provider-agnostic and lets adding a new provider
require zero changes here.

`retryable` on each class is the single source of truth for "retry the same
provider once before falling back" vs. "move to the next provider
immediately." Keep it a class attribute (not decided ad-hoc at call sites)
so the retry policy is defined in exactly one place per error kind.
"""
from __future__ import annotations


class AIProviderError(Exception):
    """Base class for all classified AI provider failures."""

    retryable: bool = False

    def __init__(self, message: str, *, provider: str | None = None, cause: BaseException | None = None):
        super().__init__(message)
        self.provider = provider
        self.cause = cause

    @property
    def category(self) -> str:
        return self.__class__.__name__


class AuthenticationError(AIProviderError):
    """Invalid/expired/missing API key. Never retryable — retrying with the
    same bad credential just burns time and, on some providers, counts
    against rate limits."""

    retryable = False


class QuotaExceededError(AIProviderError):
    """Billing/quota exhausted for the account. Not retryable within a
    request's lifetime — the quota will not reset in the next few seconds."""

    retryable = False


class RateLimitError(AIProviderError):
    """Too many requests in a short window (HTTP 429 or provider-specific
    equivalent). Retryable once with backoff — this is often transient."""

    retryable = True


class TimeoutError_(AIProviderError):
    """Request exceeded the configured timeout. Retryable once — could be a
    transient network/provider hiccup rather than a systemic outage.
    Named with a trailing underscore to avoid shadowing the builtin."""

    retryable = True


class NetworkError(AIProviderError):
    """DNS/connection-level failure reaching the provider. Retryable once."""

    retryable = True


class ProviderUnavailableError(AIProviderError):
    """Provider reachable but reporting it can't serve the request (e.g. a
    5xx from the provider itself, model overloaded). Not retried on the same
    provider — move to the next one in priority order instead."""

    retryable = False


class InvalidResponseError(AIProviderError):
    """The provider responded successfully at the transport level, but the
    payload didn't have the shape we expected (e.g. missing `choices`).
    Not retryable — the same request would produce the same shape again."""

    retryable = False


class JSONParseError(AIProviderError):
    """The provider's response text could not be parsed as the JSON schema
    we asked for. Not retryable for the same reason as InvalidResponseError.
    Kept distinct from InvalidResponseError because it's diagnostically
    useful to know "the SDK call worked, but the model didn't follow the
    JSON instruction" vs. "the SDK/transport itself misbehaved" — the former
    usually means a prompt/model problem, the latter an infra problem."""

    retryable = False


def classify_exception(exc: BaseException, *, provider: str) -> AIProviderError:
    """Best-effort classification for exceptions that a provider
    implementation didn't already wrap in one of the types above (e.g. an
    SDK raising a bare `TimeoutError` or `ConnectionError`). Provider
    implementations should prefer raising the specific classes directly
    when they can identify the cause from the SDK's own exception type;
    this is the fallback for anything that slips through.
    """
    if isinstance(exc, AIProviderError):
        return exc

    text = str(exc).lower()
    name = exc.__class__.__name__.lower()

    if "timeout" in name or "timeout" in text:
        return TimeoutError_(str(exc), provider=provider, cause=exc)
    if "connection" in name or "connection" in text or "network" in text:
        return NetworkError(str(exc), provider=provider, cause=exc)
    if "rate" in text and "limit" in text:
        return RateLimitError(str(exc), provider=provider, cause=exc)
    if "quota" in text or "billing" in text or "insufficient_quota" in text:
        return QuotaExceededError(str(exc), provider=provider, cause=exc)
    if "auth" in text or "api key" in text or "apikey" in text or "401" in text or "403" in text:
        return AuthenticationError(str(exc), provider=provider, cause=exc)
    if isinstance(exc, (ValueError,)) and ("json" in text or "expecting value" in text):
        return JSONParseError(str(exc), provider=provider, cause=exc)

    return ProviderUnavailableError(str(exc), provider=provider, cause=exc)
