"""diagnose node: turn raw test output into a structured list of failures.

LLM-backed. The system prompt forces a JSON-only array; the response is
defensively parsed (fences stripped, bug types clamped) and any parse failure
degrades to a single generic LOGIC failure rather than crashing the loop.
"""

from __future__ import annotations

import json
import logging

from agent.llm import clamp_bug_type, complete_text, strip_code_fences
from agent.state import AgentState, FailureInfo

logger = logging.getLogger(__name__)

# Tail of the test output to send — failures are usually at the end.
_MAX_OUTPUT_CHARS = 8000
_MAX_TOKENS = 4096

DIAGNOSE_SYSTEM = """You are a CI/CD failure analyst. You are given raw output \
from a failing test suite. Identify each distinct failure.

Output ONLY a valid JSON array — no markdown, no code fences, no preamble. Each \
element MUST be an object with exactly these keys:
  - "file_path": string, the source file to fix (relative path)
  - "bug_type": one of exactly LINTING | SYNTAX | LOGIC | TYPE_ERROR | IMPORT | INDENTATION
  - "line_number": integer line number, or null if unknown
  - "description": a fix instruction starting with a lowercase verb, e.g. \
"remove the unused import"
  - "raw_output": the relevant snippet of the test output for this failure

If there are no actionable failures, output an empty array []."""


def _fallback_failure(raw_output: str) -> FailureInfo:
    return FailureInfo(
        file_path="unknown",
        bug_type="LOGIC",
        line_number=None,
        description="investigate the failing test output and correct the defect",
        raw_output=raw_output[:1000],
    )


async def diagnose_failures(state: AgentState) -> dict:
    """Produce a structured failure list from the latest raw test output."""
    raw_output = state.get("raw_test_output", "") or ""
    # Keep the tail — stack traces and assertion errors land at the end.
    truncated = raw_output[-_MAX_OUTPUT_CHARS:]

    try:
        text = await complete_text(DIAGNOSE_SYSTEM, truncated, _MAX_TOKENS)
        parsed = json.loads(strip_code_fences(text))
        if not isinstance(parsed, list):
            raise ValueError("diagnose output was not a JSON array")

        failures: list[FailureInfo] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            line = item.get("line_number")
            failures.append(
                FailureInfo(
                    file_path=str(item.get("file_path", "unknown")),
                    bug_type=clamp_bug_type(item.get("bug_type")),
                    line_number=line if isinstance(line, int) else None,
                    description=str(item.get("description", "")),
                    raw_output=str(item.get("raw_output", "")),
                )
            )
        return {"failures": failures}
    except Exception:  # noqa: BLE001 — never crash the loop on a parse error
        logger.exception("diagnose failed to parse LLM output; using fallback")
        return {"failures": [_fallback_failure(truncated)]}
