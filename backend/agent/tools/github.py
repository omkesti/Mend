"""Git and GitHub operations for the agent.

Local git work (clone, branch, commit, push) uses GitPython; remote CI status
uses the GitHub REST API via PyGithub. The GitHub token is read once from
settings and injected into clone/push URLs so credentials never touch disk.
"""

from __future__ import annotations

import re

from git import Repo
from github import Github, GithubException

from config import get_settings

settings = get_settings()

# Identity stamped on agent commits.
GIT_AUTHOR_NAME = "CI/CD Healing Agent"
GIT_AUTHOR_EMAIL = "agent@mend.local"

COMMIT_PREFIX = "[AI-AGENT]"


def parse_repo_url(url: str) -> tuple[str, str]:
    """Extract ``(owner, repo_name)`` from an HTTPS or SSH GitHub URL.

    Handles a trailing ``.git``, trailing slashes, and ``git@`` SSH form.
    """
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]

    # SSH form: git@github.com:owner/repo
    ssh = re.match(r"^git@[^:]+:(?P<owner>[^/]+)/(?P<repo>[^/]+)$", cleaned)
    if ssh:
        return ssh.group("owner"), ssh.group("repo")

    # HTTPS form: https://github.com/owner/repo
    parts = cleaned.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {url!r}")
    owner, repo = parts[-2], parts[-1]
    if not owner or not repo:
        raise ValueError(f"Cannot parse owner/repo from URL: {url!r}")
    return owner, repo


def build_branch_name(team_name: str, leader_name: str) -> str:
    """``TEAM_NAME_LEADER_NAME_AI_Fix`` — uppercase, spaces to underscores."""

    def sanitize(s: str) -> str:
        return s.upper().replace(" ", "_")

    return f"{sanitize(team_name)}_{sanitize(leader_name)}_AI_Fix"


def _authenticated_url(repo_url: str) -> str:
    """Insert the GitHub token into an HTTPS remote URL for push/clone."""
    owner, repo = parse_repo_url(repo_url)
    return f"https://{settings.github_token}@github.com/{owner}/{repo}.git"


def clone_repo(repo_url: str, workspace_path: str) -> Repo:
    """Clone ``repo_url`` into ``workspace_path`` and set the commit identity."""
    repo = Repo.clone_from(_authenticated_url(repo_url), workspace_path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", GIT_AUTHOR_NAME)
        cw.set_value("user", "email", GIT_AUTHOR_EMAIL)
    return repo


def create_branch(workspace_path: str, branch_name: str) -> None:
    """Create and check out ``branch_name`` in the cloned workspace."""
    repo = Repo(workspace_path)
    # Reuse the branch if a previous iteration already created it.
    if branch_name in repo.heads:
        repo.heads[branch_name].checkout()
    else:
        repo.create_head(branch_name).checkout()


def commit_and_push(
    workspace_path: str,
    branch_name: str,
    message: str,
    repo_url: str,
) -> bool:
    """Stage everything, commit with the ``[AI-AGENT]`` prefix, push the branch.

    Returns ``False`` when the working tree is clean (nothing to commit),
    ``True`` after a successful commit and push.
    """
    repo = Repo(workspace_path)
    repo.git.add(A=True)

    # Nothing staged relative to HEAD -> nothing to commit.
    if not repo.git.status("--porcelain").strip():
        return False

    full_message = message if message.startswith(COMMIT_PREFIX) else f"{COMMIT_PREFIX} {message}"
    repo.index.commit(full_message)

    push_url = _authenticated_url(repo_url)
    # Push to origin using the token-authenticated URL without persisting it.
    repo.git.push(push_url, f"{branch_name}:{branch_name}", "--set-upstream")
    return True


def get_ci_status(owner: str, repo_name: str, branch_name: str) -> str:
    """Return the latest GitHub Actions conclusion for ``branch_name``.

    One of ``"passed" | "failed" | "pending" | "no_ci"``. On any GitHub API
    error returns ``"error:{status}"`` instead of raising.
    """
    try:
        gh = Github(settings.github_token)
        repo = gh.get_repo(f"{owner}/{repo_name}")
        runs = repo.get_workflow_runs(branch=branch_name)

        if runs.totalCount == 0:
            # No run for this branch yet. Distinguish a repo with no CI at all
            # ("no_ci") from one where the workflow simply hasn't registered a
            # run yet ("pending", so monitor_ci keeps polling) — otherwise a
            # just-pushed branch races the Actions scheduler and looks like no_ci.
            try:
                configured = repo.get_workflows().totalCount > 0
            except GithubException:
                configured = False
            return "pending" if configured else "no_ci"

        latest = runs[0]  # most recent first
        if latest.status != "completed":
            return "pending"
        return "passed" if latest.conclusion == "success" else "failed"
    except GithubException as exc:
        return f"error:{exc.status}"
    except Exception:  # defensive: a status poll must never crash the loop
        return "error:unknown"
