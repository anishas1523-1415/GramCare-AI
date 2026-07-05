"""Minimal in-memory fixed-window rate limiter.

Why not slowapi/redis: this service currently runs as a single instance
(Render free tier / one Docker container), and the repo's dependency policy
favors zero new packages where a ~40-line implementation suffices (the Node
signaling service already uses the same hand-rolled pattern for SOS).
For a multi-replica deployment this must move to a shared store — tracked
in roadmap Phase 9/10.

Usage:
    from core.ratelimit import rate_limit
    @router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
"""
import time
import threading
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)

# Kept small and bounded: periodically drop empty keys so the map can't grow
# without limit under IP churn.
_MAX_KEYS = 50_000


def _client_ip(request: Request) -> str:
    # Honor the first X-Forwarded-For hop when behind a proxy (Render/nginx),
    # falling back to the socket peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, max_requests: int, window_seconds: int):
    """Return a FastAPI dependency enforcing `max_requests` per
    `window_seconds` per client IP for the given bucket name."""

    def dependency(request: Request):
        key = f"{bucket}:{_client_ip(request)}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            # Evict timestamps outside the window
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment and try again.",
                )
            q.append(now)
            if len(_hits) > _MAX_KEYS:
                # Emergency pressure release: drop the oldest half of keys.
                for k in list(_hits.keys())[: _MAX_KEYS // 2]:
                    _hits.pop(k, None)

    return dependency


def reset_for_tests():
    """Test helper: clear all rate-limit state between test cases."""
    with _lock:
        _hits.clear()
