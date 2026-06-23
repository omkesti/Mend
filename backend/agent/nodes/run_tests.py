"""run_tests node: execute the detected test suite and capture the result.

Pivot node in the loop. A clean exit (returncode 0, no timeout) ends the graph;
any failure feeds the raw output to `diagnose`. A timeout counts as a failure
so the loop can attempt fixes rather than hanging.
"""

from __future__ import annotations

import logging

from agent.state import AgentState
from agent.tools import sandbox
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def run_tests_node(state: AgentState) -> dict:
    """Run the test command and report whether everything passed."""
    result = await sandbox.run_tests(
        state["workspace_path"],
        state["test_command"],
        state["detected_stack"],
    )

    if result["timed_out"]:
        # A suite that won't run can't be healed — stop with a clear message.
        msg = f"Test execution timed out after {settings.sandbox_timeout}s."
        logger.warning("run_tests timed out for run %s", state.get("run_id"))
        return {"all_tests_passing": False, "should_stop": True, "error": msg,
                "raw_test_output": msg}

    if result["returncode"] == 0:
        return {"all_tests_passing": True, "failures": []}

    combined = result["stdout"]
    if result["stderr"]:
        combined = f"{combined}\n{result['stderr']}" if combined else result["stderr"]

    return {"raw_test_output": combined, "all_tests_passing": False}
