"""Shared helpers for provider implementations.

This is intentionally NOT a provider itself and holds no SDK imports — just
the bit of JSON-extraction logic that would otherwise be copy-pasted
identically into every provider (the prompts instruct the model to return
raw JSON, but some models wrap it in ```json ... ``` fences anyway).
"""
from __future__ import annotations

import json
import re

from ..errors import JSONParseError

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str, *, provider: str) -> dict:
    """Best-effort extraction of a JSON object from a model's raw text
    response, tolerating markdown code fences or leading/trailing prose.
    Raises JSONParseError (never a bare json.JSONDecodeError) so AIManager's
    error-classification-based retry/fallback logic can key off it directly.
    """
    if not text or not text.strip():
        raise JSONParseError("Empty response from model", provider=provider)

    match = _JSON_BLOCK_RE.search(text)
    candidate = match.group(0) if match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        raise JSONParseError(
            f"Could not parse JSON from model response: {e}", provider=provider, cause=e
        ) from e
