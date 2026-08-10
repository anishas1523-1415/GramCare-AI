"""Every timestamp in this codebase is stored as a naive datetime that is
*actually* UTC (`datetime.utcnow()` / `datetime.now(timezone.utc).replace(
tzinfo=None)`) — Postgres columns are plain `TIMESTAMP` (no timezone), and
Pydantic serializes a naive datetime's `.isoformat()` with no 'Z' or offset
at all, e.g. "2026-07-20T14:30:00".

Per the ISO 8601 / JS Date spec, a datetime string with no timezone
designator is parsed as *local* time, not UTC. So every `new Date(x)` in
web_portal (and every `DateTime.parse(x)` in the Flutter apps) was silently
reinterpreting a UTC instant as if it were already in the browser's/
device's local zone — appointment times, SOS timestamps, lab bookings,
prescriptions, all off by the viewer's UTC offset (5:30h for IST). This is
the root cause behind "current time and selected time" bugs reported in
the doctor portal's appointment queue.

Fixing every schema's `datetime` field individually (or migrating every
column to `TIMESTAMP WITH TIME ZONE`) would touch dozens of files and
tables for a formatting bug. Instead, a custom response class post-
processes the already-JSON-encoded response body and appends 'Z' to any
bare naive-datetime-shaped string — a single, global, source-of-truth fix
that requires no schema or model changes anywhere.
"""
import re
from typing import Any

from fastapi.responses import JSONResponse

# Matches "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DDTHH:MM:SS.ffffff" with no
# trailing 'Z' or +HH:MM/-HH:MM offset (a fully-qualified string is left
# untouched, so this is safe to run over already-timezone-aware values too).
_NAIVE_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$"
)


def _tag_naive_datetimes(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _tag_naive_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_tag_naive_datetimes(v) for v in obj]
    if isinstance(obj, str) and _NAIVE_DATETIME_RE.match(obj):
        return obj + "Z"
    return obj


class UtcJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(_tag_naive_datetimes(content))
