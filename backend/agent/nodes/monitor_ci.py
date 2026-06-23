"""monitor_ci node: poll GitHub Actions and decide whether to loop or stop.

Polls with a back-off schedule until CI reaches a terminal state. When the repo
has no CI configured, the most recent local test result is treated as ground
truth. Stops the loop on pass, retry exhaustion, or a polling error.
"""

from __future__ import annotations

import asyncio
import logging

from agent.state import AgentState
from agent.tools import github

logger = logging.getLogger(__name__)

# Roughly exponential back-off (seconds) between CI status polls.
_BACKOFF_SCHEDULE = [5, 10, 15, 20, 30, 30, 30]


async def monitor_ci(state: AgentState) -> dict:
    """Resolve CI status for the pushed branch and set loop-control flags."""
    owner = state["repo_owner"]
    repo_name = state["repo_name"]
    branch = state["branch_name"]

    status = "pending"
    for i, delay in enumerate(_BACKOFF_SCHEDULE):
        status = await asyncio.to_thread(
            github.get_ci_status, owner, repo_name, branch
        )
        if status in ("passed", "failed", "no_ci") or status.startswith("error:"):
            break
        if i < len(_BACKOFF_SCHEDULE) - 1:
            await asyncio.sleep(delay)

    error_occurred = status.startswith("error:")

    if status == "passed":
        passing = True
    elif status == "failed":
        passing = False
    else:
        # "no_ci", lingering "pending", or "error:*" — fall back to local tests.
        passing = state.get("all_tests_passing", False)

    iteration = state.get("current_iteration", 0)
    should_stop = passing or iteration >= state["max_retries"] or error_occurred

    logger.info(
        "monitor_ci: status=%s passing=%s iteration=%s stop=%s",
        status, passing, iteration, should_stop,
    )

    result: dict = {"all_tests_passing": passing, "should_stop": should_stop}
    if error_occurred:
        result["error"] = f"CI polling error: {status}"
    return result
