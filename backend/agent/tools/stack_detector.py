"""Tech-stack detection via filesystem heuristics.

Detection is manifest-first: a stack is identified by the presence of its
manifest files (never by hardcoded test paths). The test command is then
refined by reading those manifests (e.g. choosing jest vs vitest, or pytest
vs unittest). Test file discovery is a recursive glob with noise directories
excluded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

# Directories never worth scanning for test files.
_EXCLUDE_DIRS = {"node_modules", ".git", "venv", ".venv", "__pycache__", ".tox"}


class StackProfile(TypedDict):
    markers: list[str]  # manifest files that identify the stack
    test_patterns: list[str]  # glob patterns for test files
    test_dirs: list[str]  # conventional test directories
    default_command: str  # fallback test command


STACK_PROFILES: dict[str, StackProfile] = {
    "python": {
        "markers": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
        "test_patterns": ["test_*.py", "*_test.py"],
        "test_dirs": ["tests", "test"],
        "default_command": "pytest --tb=short -v",
    },
    "node": {
        "markers": ["package.json"],
        "test_patterns": ["*.test.js", "*.spec.js", "*.test.ts", "*.spec.ts"],
        "test_dirs": ["test", "tests", "__tests__"],
        "default_command": "npm test",
    },
    "go": {
        "markers": ["go.mod"],
        "test_patterns": ["*_test.go"],
        "test_dirs": ["."],
        "default_command": "go test ./... -v",
    },
}


class StackInfo(TypedDict):
    stack: str
    test_command: str
    test_files: list[str]
    project_dir: str  # subdir (relative, POSIX) holding the stack; "" for root


def _iter_marker_dirs(workspace: Path, markers: list[str]):
    """Yield directories (anywhere in the tree) that contain a stack marker."""
    for marker in markers:
        for path in workspace.rglob(marker):
            if not path.is_file():
                continue
            rel = path.relative_to(workspace)
            if _EXCLUDE_DIRS & set(rel.parts):
                continue
            yield path.parent


def _find_test_files(workspace_path: str, patterns: list[str]) -> list[str]:
    """Recursively glob for test files, excluding noise dirs, relative paths."""
    workspace = Path(workspace_path)
    found: list[str] = []
    for pattern in patterns:
        for path in workspace.rglob(pattern):
            if not path.is_file():
                continue
            if _EXCLUDE_DIRS & set(path.relative_to(workspace).parts):
                continue
            found.append(path.relative_to(workspace).as_posix())
    return sorted(set(found))


def _detect_test_command(
    workspace_path: str, stack: str, profile: StackProfile
) -> str:
    """Pick the most specific test runner by reading the stack's manifests."""
    workspace = Path(workspace_path)

    if stack == "python":
        # Prefer pytest if available/configured, else fall back to unittest.
        pyproject = workspace / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8", errors="ignore") if pyproject.exists() else ""
        reqs = workspace / "requirements.txt"
        reqs_text = reqs.read_text(encoding="utf-8", errors="ignore") if reqs.exists() else ""
        if "pytest" in text or "pytest" in reqs_text or (workspace / "pytest.ini").exists():
            return "pytest --tb=short -v"
        # No pytest signal: unittest discovery is always available.
        return "python -m unittest discover -v"

    if stack == "node":
        pkg = workspace / "package.json"
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            return profile["default_command"]

        scripts = data.get("scripts", {})
        if isinstance(scripts, dict) and scripts.get("test"):
            return "npm test"

        # No test script: detect the installed runner directly.
        deps = {
            **data.get("devDependencies", {}),
            **data.get("dependencies", {}),
        }
        for runner in ("vitest", "jest", "mocha"):
            if runner in deps:
                return f"npx {runner}"
        return profile["default_command"]

    # go and anything else: the default command is already correct.
    return profile["default_command"]


def detect_projects(workspace_path: str) -> list[StackInfo]:
    """Detect every distinct (stack, directory) project in the repo.

    Returns all projects so a monorepo with, say, a Python `backend/` and a Node
    `frontend/` can be healed together. Each entry's `test_files` are relative to
    that project's `project_dir`; `project_dir` is "" for a project at the root.
    """
    workspace = Path(workspace_path)
    seen: set[tuple[str, str]] = set()
    projects: list[StackInfo] = []

    for stack, profile in STACK_PROFILES.items():
        for found_dir in _iter_marker_dirs(workspace, profile["markers"]):
            key = (stack, str(found_dir))
            if key in seen:
                continue
            seen.add(key)
            rel = found_dir.relative_to(workspace).as_posix()
            projects.append(
                StackInfo(
                    stack=stack,
                    test_command=_detect_test_command(str(found_dir), stack, profile),
                    test_files=_find_test_files(str(found_dir), profile["test_patterns"]),
                    project_dir="" if rel == "." else rel,
                )
            )

    # Drop a project whose dir is an ancestor of a deeper project of the same
    # stack — e.g. an aggregate root `requirements.txt` that just re-exports a
    # sub-project. The deeper, more specific project is the real one, and the
    # ancestor would otherwise run tests from the wrong directory.
    return [p for p in projects if not _is_shadowed(p, projects)]


def _is_shadowed(project: StackInfo, projects: list[StackInfo]) -> bool:
    pdir = project["project_dir"]
    for other in projects:
        if other is project or other["stack"] != project["stack"]:
            continue
        odir = other["project_dir"]
        if pdir == "" and odir != "":
            return True
        if odir.startswith(pdir + "/") and pdir != "":
            return True
    return False
