"""analyze_repo node: clone the repo, branch, detect the stack, install deps.

First node in the graph. Sets up the workspace and all the fields later nodes
depend on. Any failure here is terminal — there is nothing to test or fix — so
it stops the graph via `should_stop` rather than raising.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from agent.state import AgentState
from agent.tools import github, sandbox, stack_detector
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def analyze_repo(state: AgentState) -> dict:
    """Prepare the workspace and detect how to test the repo."""
    workspace_path = os.path.join(settings.workspace_dir, state["run_id"])
    started_at = datetime.now(timezone.utc).isoformat()

    try:
        owner, repo_name = github.parse_repo_url(state["repo_url"])

        github.clone_repo(state["repo_url"], workspace_path)
        github.create_branch(workspace_path, state["branch_name"])

        detected = stack_detector.detect_projects(workspace_path)

        base = {
            "workspace_path": workspace_path,
            "branch_name": state["branch_name"],
            "repo_owner": owner,
            "repo_name": repo_name,
            "started_at": started_at,
            "current_iteration": 0,
            "all_tests_passing": False,
        }

        if not detected:
            logger.warning("Unknown stack for run %s — stopping", state["run_id"])
            return {**base, "detected_stack": "unknown", "projects": [],
                    "should_stop": True,
                    "error": "Could not detect a supported tech stack (python, node, go)."}

        # Heal every project that actually has tests.
        testable = [p for p in detected if p["test_files"]]
        detected_summary = ", ".join(sorted({p["stack"] for p in detected}))

        if not testable:
            logger.warning("No test files found for run %s — stopping", state["run_id"])
            return {**base, "detected_stack": detected_summary, "projects": [],
                    "should_stop": True,
                    "error": f"No test files found in the repository (detected {detected_summary})."}

        projects = []
        for p in testable:
            project_dir = os.path.join(workspace_path, p["project_dir"]) if p["project_dir"] else workspace_path
            await sandbox.install_dependencies(project_dir, p["stack"])
            projects.append({"stack": p["stack"], "project_dir": project_dir,
                             "test_command": p["test_command"]})

        logger.info("run %s: healing %s project(s): %s", state["run_id"], len(projects),
                    ", ".join(f"{p['stack']}@{p['project_dir']}" for p in projects))

        return {**base, "detected_stack": ", ".join(sorted({p["stack"] for p in projects})),
                "projects": projects, "should_stop": False, "error": None}
    except Exception as exc:  # noqa: BLE001 — terminal setup failure, report it
        logger.exception("analyze_repo failed for run %s", state["run_id"])
        return {
            "workspace_path": workspace_path,
            "projects": [],
            "started_at": started_at,
            "current_iteration": 0,
            "all_tests_passing": False,
            "should_stop": True,
            "error": str(exc),
        }
