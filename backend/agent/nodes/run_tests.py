"""run_tests node: execute every project's suite and collect failing ones.

Pivot node in the loop. If all projects pass, the graph ends. Any project that
fails contributes a FailingProject (tagged with its dir + stack) for diagnose to
work through. A timeout in any project is terminal — a suite that won't run
can't be healed.
"""

from __future__ import annotations

import logging

from agent.state import AgentState, FailingProject
from agent.tools import sandbox
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_tests_node(state: AgentState) -> dict:
    """Run each project's test command; report failures per project."""
    failing: list[FailingProject] = []

    for project in state["projects"]:
        result = await sandbox.run_tests(
            project["project_dir"], project["test_command"], project["stack"]
        )

        if result["timed_out"]:
            msg = f"Test execution timed out after {settings.sandbox_timeout}s ({project['stack']} @ {project['project_dir']})."
            logger.warning("run_tests timed out for run %s", state.get("run_id"))
            return {"all_tests_passing": False, "should_stop": True, "error": msg,
                    "failing_projects": []}

        if result["returncode"] != 0:
            combined = result["stdout"]
            if result["stderr"]:
                combined = f"{combined}\n{result['stderr']}" if combined else result["stderr"]
            failing.append(FailingProject(
                project_dir=project["project_dir"], stack=project["stack"],
                raw_output=combined,
            ))

    if not failing:
        return {"all_tests_passing": True, "failures": [], "failing_projects": []}

    return {"all_tests_passing": False, "failing_projects": failing}
