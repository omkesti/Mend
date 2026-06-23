"""AgentState and its component TypedDicts — the contract shared by all nodes.

Every node is `async def node(state: AgentState) -> dict` and returns ONLY the
keys it changed. `fixes` and `ci_results` use the LangGraph `add` reducer, so
returning a list for them appends rather than overwrites.

The agent heals an entire repository, which may be a monorepo containing several
independently-testable projects (e.g. a Python `backend/` and a Node
`frontend/`). Each project is one `ProjectInfo`; failures and fixes are tagged
with the project they belong to so the right files get read and written.
"""

from operator import add
from typing import Annotated, Optional, TypedDict


class ProjectInfo(TypedDict):
    """One testable project within the repo."""

    stack: str  # "python" | "node" | "go"
    project_dir: str  # absolute dir where this project's tests run
    test_command: str


class FailingProject(TypedDict):
    """A project whose tests failed this iteration (produced by run_tests)."""

    project_dir: str  # absolute
    stack: str
    raw_output: str


class FailureInfo(TypedDict):
    """A single diagnosed failure produced by the `diagnose` node."""

    file_path: str  # relative to project_dir
    project_dir: str  # absolute dir of the owning project
    bug_type: str  # one of the 6 valid bug types; clamp to LINTING otherwise
    line_number: Optional[int]
    description: str  # starts with a lowercase verb: "remove the unused import"
    raw_output: str  # the relevant snippet from the test output


class FixInfo(TypedDict):
    """A single fix attempt produced by the `generate_fixes` node."""

    file_path: str  # repo-root-relative (e.g. "backend/calc.py") for display
    bug_type: str
    line_number: Optional[int]
    commit_message: str  # e.g. "Fix LINTING in backend/utils.py line 15"
    description: str  # "LINTING error in backend/utils.py line 15 -> Fix: ..."
    status: str  # "fixed" | "failed"
    patch: Optional[str]  # LLM explanation of what changed


class CIResult(TypedDict):
    """One CI loop iteration result, appended by `commit_fixes` / `monitor_ci`."""

    iteration: int
    status: str  # "passed" | "failed" | "pending" | "no_ci"
    failures_found: int
    fixes_applied: int
    timestamp: str  # ISO-8601 UTC
    log_summary: str


class AgentState(TypedDict):
    """Single source of truth threaded through the LangGraph StateGraph."""

    # Input (set before the graph starts)
    run_id: str
    repo_url: str
    team_name: str
    leader_name: str
    branch_name: str
    max_retries: int

    # Set by analyze_repo
    workspace_path: str  # git repo root (clone target)
    repo_owner: str
    repo_name: str
    detected_stack: str  # summary, e.g. "python" or "python, node"
    projects: list[ProjectInfo]  # every testable project in the repo

    # Set by run_tests
    failing_projects: list[FailingProject]

    # Set by diagnose
    failures: list[FailureInfo]

    # Accumulated across all iterations (Annotated add reducer)
    fixes: Annotated[list[FixInfo], add]
    ci_results: Annotated[list[CIResult], add]

    # Loop control
    current_iteration: int
    all_tests_passing: bool
    should_stop: bool
    error: Optional[str]

    # Timing
    started_at: str  # ISO-8601 UTC
