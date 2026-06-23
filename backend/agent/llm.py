"""Anthropic client factory and LLM-related helpers shared by agent nodes.

Centralizes the async client and the JSON-extraction helpers so the diagnose
and fix nodes don't each re-implement fence stripping or bug-type clamping.
"""

from __future__ import annotations

import re

from anthropic import AsyncAnthropic

from config import get_settings

settings = get_settings()

# The fixed bug-type enum. Anything the LLM emits outside this set is clamped
# to LINTING (the documented fallback).
VALID_BUG_TYPES: frozenset[str] = frozenset(
    {"LINTING", "SYNTAX", "LOGIC", "TYPE_ERROR", "IMPORT", "INDENTATION"}
)
FALLBACK_BUG_TYPE = "LINTING"

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Return a lazily-constructed, process-wide async Anthropic client."""
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def clamp_bug_type(value: str | None) -> str:
    """Normalize an LLM-supplied bug type to the valid enum, else LINTING."""
    if isinstance(value, str) and value.upper() in VALID_BUG_TYPES:
        return value.upper()
    return FALLBACK_BUG_TYPE


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def strip_code_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences the model may have added."""
    cleaned = text.strip()
    cleaned = _FENCE_RE.sub("", cleaned)
    return cleaned.strip()


async def complete_text(system: str, prompt: str, max_tokens: int) -> str:
    """Send a single-turn request and return the concatenated text output."""
    response = await get_client().messages.create(
        model=settings.model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
