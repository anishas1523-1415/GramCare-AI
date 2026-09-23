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
import hashlib
import logging
import os
import time
import threading
from collections import defaultdict, deque

from fastapi import HTTPException, Request

logger = logging.getLogger("gramcare.ratelimit")

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)

# Kept small and bounded: periodically drop empty keys so the map can't grow
# without limit under IP churn.
_MAX_KEYS = 50_000


def _client_ip(request: Request) -> str:
    # Behind a single trusted reverse proxy (Render's edge), X-Forwarded-For
    # is a comma-separated list where each hop APPENDS the peer IP it
    # actually observed over TCP. The LAST entry is therefore always the one
    # our own trusted proxy appended — trustworthy. Every entry before that
    # was copied verbatim from whatever header the connecting party sent and
    # is fully attacker-controlled: a direct (or spoofed) caller can set
    # X-Forwarded-For to a fresh random value on every request to get a
    # brand-new rate-limit bucket each time, defeating every limiter in this
    # module (login, register, OTP, password reset, etc.). Taking the FIRST
    # hop, as this used to do, trusted exactly the part of the header an
    # attacker controls.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _caller_key(request: Request) -> str:
    """Who this request counts against.

    The bearer token, when present, identifies one account regardless of
    which network it is on; otherwise the source IP. The token is hashed
    rather than used raw so a limiter dict can never become somewhere
    credentials sit in memory in plaintext.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 16:
        return "u:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:32]
    return "ip:" + _client_ip(request)


def rate_limit(bucket: str, max_requests: int, window_seconds: int):
    """Return a FastAPI dependency enforcing `max_requests` per
    `window_seconds` per client IP for the given bucket name."""

    def dependency(request: Request):
        # Keyed on the caller, not just their IP. A whole village behind one
        # clinic router shared a single bucket, so one person's retries
        # throttled everyone else's — including their SOS. An Authorization
        # header identifies the caller directly; anonymous traffic still
        # falls back to IP.
        key = f"{bucket}:{_caller_key(request)}"
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


def warn_if_counters_are_split() -> None:
    """Say so at boot when these counters stop meaning anything.

    Every count lives in this process's memory. With more than one worker
    each gets its own independent allowance, so the real limit silently
    becomes N times what it says — including the login brute-force and
    SOS-spam limits. Called from main.py at startup.
    """
    try:
        workers = int(os.getenv("WEB_CONCURRENCY", "1"))
    except ValueError:
        workers = 1
    if workers > 1:
        logger.error(
            "WEB_CONCURRENCY=%d but rate limiting is per-process and in-memory: "
            "every limit is effectively %dx looser than configured. Move the "
            "limiter to shared storage before scaling workers.",
            workers, workers,
        )
