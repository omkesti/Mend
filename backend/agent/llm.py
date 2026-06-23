"""Groq client factory and LLM-related helpers shared by agent nodes.

Centralizes the async client and the JSON-extraction helpers so the diagnose
and fix nodes don't each re-implement fence stripping or bug-type clamping.
The backend is Groq (OpenAI-compatible chat completions); the model is set via
`settings.model` (e.g. llama-3.3-70b-versatile).
"""

from __future__ import annotations

import asyncio
import logging
import re

from groq import APIStatusError, AsyncGroq, RateLimitError

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Groq returns 429 or 413 (rate_limit_exceeded) when the per-minute token
# budget is hit; back off and retry rather than failing the node.
_RATE_LIMIT_STATUSES = {429, 413}
_RATE_LIMIT_BACKOFF_SECONDS = 20
_MAX_RATE_LIMIT_RETRIES = 3

# The fixed bug-type enum. Anything the LLM emits outside this set is clamped
# to LINTING (the documented fallback).
VALID_BUG_TYPES: frozenset[str] = frozenset(
    {"LINTING", "SYNTAX", "LOGIC", "TYPE_ERROR", "IMPORT", "INDENTATION"}
)
FALLBACK_BUG_TYPE = "LINTING"

_client: AsyncGroq | None = None


def get_client() -> AsyncGroq:
    """Return a lazily-constructed, process-wide async Groq client."""
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
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
    """Send a single-turn chat completion, retrying on rate-limit errors."""
    for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
        try:
            response = await get_client().chat.completions.create(
                model=settings.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content or ""
        except (RateLimitError, APIStatusError) as exc:
            status = getattr(exc, "status_code", None)
            if status in _RATE_LIMIT_STATUSES and attempt < _MAX_RATE_LIMIT_RETRIES:
                logger.warning(
                    "Groq rate limit (%s); backing off %ss (attempt %s)",
                    status, _RATE_LIMIT_BACKOFF_SECONDS, attempt + 1,
                )
                await asyncio.sleep(_RATE_LIMIT_BACKOFF_SECONDS)
                continue
            raise
    raise RuntimeError("unreachable")  # loop either returns or raises
