"""In-memory AI usage metrics (requirement #8).

Same rationale as core/ratelimit.py: single-instance deployment today, so a
thread-safe in-memory counter is sufficient and adds zero new dependencies.
For a multi-replica deployment this should be replaced with a shared
store (e.g. Prometheus pushgateway / Redis) — the public interface here
(`record_request`, `record_failure`, `snapshot`) is intentionally small so
swapping the backing store later doesn't require touching call sites in
manager.py.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _ProviderTaskStats:
    requests: int = 0
    failures: int = 0
    failures_by_type: dict = field(default_factory=lambda: defaultdict(int))
    latency_ms_sum: float = 0.0
    latency_ms_count: int = 0

    @property
    def average_latency_ms(self) -> float:
        if self.latency_ms_count == 0:
            return 0.0
        return round(self.latency_ms_sum / self.latency_ms_count, 1)


class AIMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._stats: dict[tuple[str, str], _ProviderTaskStats] = defaultdict(_ProviderTaskStats)
        self._fallback_count: dict[str, int] = defaultdict(int)
        self._started_at = time.time()

    def record_success(self, provider: str, task: str, latency_ms: float) -> None:
        with self._lock:
            s = self._stats[(provider, task)]
            s.requests += 1
            s.latency_ms_sum += latency_ms
            s.latency_ms_count += 1

    def record_failure(self, provider: str, task: str, error_category: str, latency_ms: float) -> None:
        with self._lock:
            s = self._stats[(provider, task)]
            s.requests += 1
            s.failures += 1
            s.failures_by_type[error_category] += 1
            s.latency_ms_sum += latency_ms
            s.latency_ms_count += 1

    def record_fallback(self, task: str) -> None:
        """A fallback happened for `task` — i.e. the first-choice provider
        did not end up serving the request."""
        with self._lock:
            self._fallback_count[task] += 1

    def snapshot(self) -> dict:
        """Point-in-time metrics dump, safe to serialize directly as JSON
        for an admin/metrics endpoint."""
        with self._lock:
            by_provider: dict = {}
            for (provider, task), s in self._stats.items():
                by_provider.setdefault(provider, {})[task] = {
                    "requests": s.requests,
                    "failures": s.failures,
                    "failures_by_type": dict(s.failures_by_type),
                    "average_latency_ms": s.average_latency_ms,
                }
            return {
                "uptime_seconds": round(time.time() - self._started_at, 1),
                "by_provider": by_provider,
                "fallback_count_by_task": dict(self._fallback_count),
            }

    def reset_for_tests(self) -> None:
        with self._lock:
            self._stats.clear()
            self._fallback_count.clear()


# Process-wide singleton — mirrors the pattern already used by
# core/ratelimit.py's module-level state.
ai_metrics = AIMetrics()
