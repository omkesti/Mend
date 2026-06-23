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

        stack_info = stack_detector.detect_stack(workspace_path)

        if stack_info["stack"] == "unknown":
            logger.warning("Unknown stack for run %s — stopping", state["run_id"])
            return {
                "workspace_path": workspace_path,
                "repo_owner": owner,
                "repo_name": repo_name,
                "detected_stack": "unknown",
                "test_command": "",
                "test_files": [],
                "started_at": started_at,
                "current_iteration": 0,
                "all_tests_passing": False,
                "should_stop": True,
                "error": "Could not detect a supported tech stack (python, node, go).",
            }

        if not stack_info["test_files"]:
            logger.warning("No test files found for run %s — stopping", state["run_id"])
            return {
                "workspace_path": workspace_path,
                "branch_name": state["branch_name"],
                "repo_owner": owner,
                "repo_name": repo_name,
                "detected_stack": stack_info["stack"],
                "test_command": stack_info["test_command"],
                "test_files": [],
                "started_at": started_at,
                "current_iteration": 0,
                "all_tests_passing": False,
                "should_stop": True,
                "error": f"No test files found in the repository (detected {stack_info['stack']} stack).",
            }

        await sandbox.install_dependencies(workspace_path, stack_info["stack"])

        return {
            "workspace_path": workspace_path,
            "branch_name": state["branch_name"],
            "repo_owner": owner,
            "repo_name": repo_name,
            "detected_stack": stack_info["stack"],
            "test_command": stack_info["test_command"],
            "test_files": stack_info["test_files"],
            "started_at": started_at,
            "current_iteration": 0,
            "all_tests_passing": False,
            "should_stop": False,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — terminal setup failure, report it
        logger.exception("analyze_repo failed for run %s", state["run_id"])
        return {
            "workspace_path": workspace_path,
            "started_at": started_at,
            "current_iteration": 0,
            "all_tests_passing": False,
            "should_stop": True,
            "error": str(exc),
        }
