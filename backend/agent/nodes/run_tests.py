"""run_tests node: execute the detected test suite and capture the result.

Pivot node in the loop. A clean exit (returncode 0, no timeout) ends the graph;
any failure feeds the raw output to `diagnose`. A timeout counts as a failure
so the loop can attempt fixes rather than hanging.
"""

from __future__ import annotations

import logging

from agent.state import AgentState
from agent.tools import sandbox

logger = logging.getLogger(__name__)


async def run_tests_node(state: AgentState) -> dict:
    """Run the test command and report whether everything passed."""
    result = await sandbox.run_tests(
        state["workspace_path"],
        state["test_command"],
        state["detected_stack"],
    )

    if result["returncode"] == 0 and not result["timed_out"]:
        return {"all_tests_passing": True, "failures": []}

    combined = result["stdout"]
    if result["stderr"]:
        combined = f"{combined}\n{result['stderr']}" if combined else result["stderr"]

    return {"raw_test_output": combined, "all_tests_passing": False}
