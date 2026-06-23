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


def _has_marker(workspace: Path, markers: list[str]) -> bool:
    return any((workspace / marker).exists() for marker in markers)


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


def detect_stack(workspace_path: str) -> StackInfo:
    """Detect the stack and resolve its test command and test files."""
    workspace = Path(workspace_path)

    for stack, profile in STACK_PROFILES.items():
        if _has_marker(workspace, profile["markers"]):
            test_command = _detect_test_command(workspace_path, stack, profile)
            test_files = _find_test_files(workspace_path, profile["test_patterns"])
            return StackInfo(
                stack=stack,
                test_command=test_command,
                test_files=test_files,
            )

    logger.warning("Could not detect stack in %s — no known manifest found", workspace_path)
    return StackInfo(stack="unknown", test_command="", test_files=[])
