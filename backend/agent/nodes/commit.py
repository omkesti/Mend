"""commit node: commit this iteration's successful fixes and push the branch.

Records a CIResult with status "pending" for every iteration — even when there
was nothing to commit — so the dashboard timeline reflects the loop accurately.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from agent.state import AgentState, CIResult
from agent.tools import github

logger = logging.getLogger(__name__)


async def commit_fixes(state: AgentState) -> dict:
    """Commit/push the fixes produced this iteration and append a CIResult."""
    iteration = state.get("current_iteration", 0) + 1

    failures = state.get("failures", [])
    all_fixes = state.get("fixes", [])

    # generate_fixes appended exactly one FixInfo per current failure, so this
    # iteration's fixes are the trailing len(failures) entries.
    n = len(failures)
    iteration_fixes = all_fixes[-n:] if n else []
    fixed = [f for f in iteration_fixes if f["status"] == "fixed"]

    bug_types = sorted({f["bug_type"] for f in fixed})
    types_str = ", ".join(bug_types) if bug_types else "no changes"
    message = f"Iteration {iteration}: fix {len(fixed)} issue(s) ({types_str})"

    try:
        committed = await asyncio.to_thread(
            github.commit_and_push,
            state["workspace_path"],
            state["branch_name"],
            message,
            state["repo_url"],
        )
        if not committed:
            logger.info("Iteration %s: nothing to commit", iteration)
    except Exception:  # noqa: BLE001 — still record the iteration on push failure
        logger.exception("commit_fixes: push failed on iteration %s", iteration)

    ci_result = CIResult(
        iteration=iteration,
        status="pending",  # monitor_ci determines the real outcome
        failures_found=len(failures),
        fixes_applied=len(fixed),
        timestamp=datetime.now(timezone.utc).isoformat(),
        log_summary=message,
    )

    return {"current_iteration": iteration, "ci_results": [ci_result]}
