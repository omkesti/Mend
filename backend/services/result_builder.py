"""Assemble the final results dict and write results.json.

The output shape mirrors the `results.json` schema in project_context.md
exactly. `compute_score` is called internally.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from agent.state import AgentState
from services.scorer import compute_score

logger = logging.getLogger(__name__)


def _duration_seconds(started_at: str, finished_at: str) -> float:
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
        return round((end - start).total_seconds(), 1)
    except (ValueError, TypeError):
        return 0.0


def _final_status(state: AgentState) -> str:
    if state.get("error"):
        return "failed"
    return "passed" if state.get("all_tests_passing") else "failed"


def build_results(state: AgentState, started_at: str) -> dict:
    """Assemble the full results dict for a finished run."""
    finished_at = datetime.now(timezone.utc).isoformat()
    duration = _duration_seconds(started_at, finished_at)

    fixes = state.get("fixes", [])
    ci_results = state.get("ci_results", [])

    total_failures = len(fixes)
    total_fixes_applied = sum(1 for f in fixes if f["status"] == "fixed")
    total_commits = len(ci_results)
    status = _final_status(state)

    # The stored CIResults are "pending" (monitor_ci doesn't mutate them via the
    # reducer). Reconcile the final iteration's status to the run's real outcome.
    timeline = [dict(cr) for cr in ci_results]
    if timeline:
        timeline[-1]["status"] = "passed" if status == "passed" else "failed"

    # A run only earns a score if it actually healed the repo. A failed or
    # aborted run (bad clone, no tests, unsupported stack, retries exhausted)
    # scores 0 — otherwise a fast failure would misleadingly show ~110.
    if status == "passed":
        score = compute_score(duration, total_commits)
    else:
        score = {"base_score": 0, "speed_bonus": 0, "efficiency_penalty": 0, "final_score": 0}

    return {
        "run_id": state.get("run_id"),
        "repo_url": state.get("repo_url"),
        "team_name": state.get("team_name"),
        "leader_name": state.get("leader_name"),
        "branch_name": state.get("branch_name"),
        "detected_stack": state.get("detected_stack"),
        "status": status,
        "total_failures": total_failures,
        "total_fixes_applied": total_fixes_applied,
        "total_commits": total_commits,
        "duration_seconds": duration,
        "score": score,
        "fixes": [
            {
                "file": f["file_path"],
                "bug_type": f["bug_type"],
                "line_number": f.get("line_number"),
                "commit_message": f["commit_message"],
                "description": f["description"],
                "status": f["status"],
            }
            for f in fixes
        ],
        "ci_timeline": timeline,
        "error": state.get("error"),
        "started_at": started_at,
        "finished_at": finished_at,
    }


def write_results_json(results: dict, workspace_path: str) -> None:
    """Write the results dict as results.json at the workspace root."""
    if not workspace_path:
        logger.warning("write_results_json: no workspace_path; skipping")
        return
    path = os.path.join(workspace_path, "results.json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
    except OSError:
        logger.exception("write_results_json: failed to write %s", path)
