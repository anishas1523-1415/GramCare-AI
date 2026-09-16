"""Multiple API keys per provider, rotated when one runs out of quota.

Every provider GramCare AI uses is on a free tier with a *daily* request
cap. One key means that when the cap is hit, every AI feature in every app
— triage, prescription OCR, medicine information, doctor summaries — falls
through to MockProvider's "AI Engines Unavailable" for the rest of the day.
That is exactly the failure users reported: the assistant appears to work
once and then not at all.

Rotation turns N free keys into N times the daily headroom, and because a
daily cap resets on the provider's clock rather than ours, an exhausted key
is put on a cooldown and retried afterwards rather than discarded.

The pool is deliberately in-process and unsynchronised across workers: two
workers may each discover a key is exhausted before either records it,
which costs one wasted call per worker, not correctness. Sharing this state
would mean a round trip to the database on the hot path of every AI
request, which is the wrong trade for a rural deployment on a slow link.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Iterator, Optional

logger = logging.getLogger("gramcare.ai.keypool")

#: How long an exhausted key sits out before it is tried again. Provider
#: daily caps reset on a fixed clock (midnight Pacific for Gemini), so a
#: fixed hour-long cooldown is a compromise: long enough not to waste calls
#: hammering a spent key, short enough that the pool recovers on its own
#: within an hour of the real reset without a deploy or restart.
DEFAULT_COOLDOWN_SECONDS = 3600.0

#: A short cooldown for per-minute rate limits, which recover in seconds.
RATE_LIMIT_COOLDOWN_SECONDS = 75.0


def _mask(key: str) -> str:
    """Keys must never reach a log intact. Enough tail to tell two keys
    apart when reading logs, never enough to use one."""
    return f"...{key[-4:]}" if len(key) >= 4 else "..."


@dataclass
class _KeyState:
    key: str
    cooling_until: float = 0.0
    #: Number of times this key has been marked exhausted, for /ai/health.
    exhaustions: int = 0

    def is_cooling(self, now: float) -> bool:
        return now < self.cooling_until


@dataclass
class KeyPool:
    """An ordered set of interchangeable API keys for one provider."""

    provider: str
    _states: list[_KeyState] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def from_keys(cls, provider: str, keys: list[str]) -> "KeyPool":
        seen: set[str] = set()
        states: list[_KeyState] = []
        for raw in keys:
            key = raw.strip()
            # A duplicated key is not extra headroom — it is the same quota
            # counted twice, and would make the pool look healthier than it
            # is. Drop repeats rather than pretend.
            if not key or key in seen:
                continue
            seen.add(key)
            states.append(_KeyState(key=key))
        return cls(provider=provider, _states=states)

    @classmethod
    def from_env(cls, provider: str, plural_var: str, singular_var: str) -> "KeyPool":
        """Reads `plural_var` (comma- or whitespace-separated) and merges in
        `singular_var`, so an existing single-key deployment keeps working
        untouched and gains rotation simply by setting the plural one."""
        raw = os.getenv(plural_var) or ""
        keys = [part for chunk in raw.split(",") for part in chunk.split()]
        single = (os.getenv(singular_var) or "").strip()
        if single:
            keys.append(single)
        return cls.from_keys(provider, keys)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._states)

    @property
    def configured(self) -> bool:
        return bool(self._states)

    def available_count(self, now: Optional[float] = None) -> int:
        now = time.monotonic() if now is None else now
        return sum(1 for s in self._states if not s.is_cooling(now))

    def all_exhausted(self) -> bool:
        """True when every key is cooling off. Distinct from "no keys
        configured" — the apps show a different message for each, because
        one is something the user can fix with their own key and the other
        is an operator misconfiguration."""
        return self.configured and self.available_count() == 0

    def seconds_until_recovery(self) -> Optional[float]:
        """When the soonest key comes back, for surfacing a real wait time
        instead of a bare failure."""
        if not self._states:
            return None
        now = time.monotonic()
        soonest = min(s.cooling_until for s in self._states)
        return max(0.0, soonest - now)

    def snapshot(self) -> list[dict]:
        """Masked, for the admin /ai/health endpoint."""
        now = time.monotonic()
        return [
            {
                "key": _mask(s.key),
                "cooling": s.is_cooling(now),
                "cooling_seconds_left": round(max(0.0, s.cooling_until - now), 1),
                "exhaustions": s.exhaustions,
            }
            for s in self._states
        ]

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def usable_keys(self) -> Iterator[str]:
        """Yields every key that is not cooling, in configured order.

        Callers iterate this and stop at the first success, so the ordering
        doubles as priority: put the key with the most headroom first.
        """
        now = time.monotonic()
        for state in self._states:
            if not state.is_cooling(now):
                yield state.key

    def first_usable(self) -> Optional[str]:
        return next(self.usable_keys(), None)

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------
    def mark_exhausted(self, key: str, cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        for state in self._states:
            if state.key == key:
                state.cooling_until = time.monotonic() + cooldown_seconds
                state.exhaustions += 1
                logger.warning(
                    "ai_keypool provider=%s key=%s exhausted cooldown_s=%.0f remaining_keys=%d",
                    self.provider, _mask(key), cooldown_seconds, self.available_count(),
                )
                return

    def mark_rate_limited(self, key: str) -> None:
        self.mark_exhausted(key, RATE_LIMIT_COOLDOWN_SECONDS)

    def mark_ok(self, key: str) -> None:
        """A key that answers is healthy again — clear any cooldown early so
        a key that was only briefly rate limited returns to full use."""
        for state in self._states:
            if state.key == key:
                state.cooling_until = 0.0
                return
