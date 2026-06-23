"""fix node: read each failing file, ask the LLM for a corrected version.

One LLM call per file (failures grouped), not one per failure. The full file
content is sent so the model has complete context. A missing file or a parse
failure marks that file's fixes as failed and continues — never crashes.
"""

from __future__ import annotations

import json
import logging
import os

from agent.llm import complete_text, strip_code_fences
from agent.state import AgentState, FailureInfo, FixInfo

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096

FIX_SYSTEM = """You are an expert software engineer fixing a failing file. You \
are given the full current contents of one file and a list of failures in it.

Rewrite the file to fix ALL listed failures while preserving unrelated code and \
behavior. Output ONLY valid JSON — no markdown, no code fences, no preamble — \
with exactly these keys:
  - "fixed_content": the complete corrected file as a single string, or null if \
you cannot produce a fix
  - "explanation": one short line describing what you changed"""


def _location(failure: FailureInfo) -> str:
    ln = failure.get("line_number")
    return f" line {ln}" if ln is not None else ""


def _make_fix(failure: FailureInfo, status: str, explanation: str | None) -> FixInfo:
    loc = _location(failure)
    bug_type = failure["bug_type"]
    path = failure["file_path"]
    return FixInfo(
        file_path=path,
        bug_type=bug_type,
        line_number=failure.get("line_number"),
        commit_message=f"Fix {bug_type} in {path}{loc}",
        description=f"{bug_type} error in {path}{loc} → Fix: {failure['description']}",
        status=status,
        patch=explanation,
    )


def _build_prompt(file_path: str, content: str, failures: list[FailureInfo]) -> str:
    lines = [f"File: {file_path}", "", "Failures:"]
    for f in failures:
        lines.append(
            f"- [{f['bug_type']}]{_location(f)}: {f['description']}"
        )
    lines += ["", "Current file content:", "```", content, "```"]
    return "\n".join(lines)


async def generate_fixes(state: AgentState) -> dict:
    """Generate and apply fixes for the current failures, grouped by file."""
    workspace = state["workspace_path"]
    failures = state.get("failures", [])

    # Group failures by file so each file gets exactly one LLM call.
    by_file: dict[str, list[FailureInfo]] = {}
    for failure in failures:
        by_file.setdefault(failure["file_path"], []).append(failure)

    fixes: list[FixInfo] = []

    for file_path, file_failures in by_file.items():
        abs_path = os.path.join(workspace, file_path)
        try:
            with open(abs_path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            logger.warning("fix: cannot read %s; marking failures failed", abs_path)
            fixes.extend(_make_fix(f, "failed", None) for f in file_failures)
            continue

        try:
            text = await complete_text(
                FIX_SYSTEM, _build_prompt(file_path, content, file_failures), _MAX_TOKENS
            )
            data = json.loads(strip_code_fences(text))
            fixed_content = data.get("fixed_content")
            explanation = str(data.get("explanation", ""))

            if not isinstance(fixed_content, str):
                raise ValueError("fixed_content missing or not a string")

            with open(abs_path, "w", encoding="utf-8") as fh:
                fh.write(fixed_content)

            fixes.extend(_make_fix(f, "fixed", explanation) for f in file_failures)
        except Exception:  # noqa: BLE001 — one bad file must not stop the rest
            logger.exception("fix: failed to fix %s", file_path)
            fixes.extend(_make_fix(f, "failed", None) for f in file_failures)

    return {"fixes": fixes}
