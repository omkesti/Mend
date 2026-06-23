"""Sandboxed subprocess execution for test and install commands.

Commands run via `asyncio` subprocesses with a hard timeout and a deliberately
minimal environment, so a target repo's test suite cannot read host secrets
(API keys, tokens) that live in the server process's environment.

This is process-level isolation only — not a container. Docker isolation is a
documented future hardening step.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
from pathlib import Path
from typing import TypedDict

from config import get_settings

settings = get_settings()


class CommandResult(TypedDict):
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


# Per-stack dependency install commands. None -> nothing to install.
_INSTALL_COMMANDS: dict[str, str | None] = {
    "python": "pip install -r requirements.txt",
    "node": "npm install",
    "go": "go mod download",
    "unknown": None,
}


def _build_env(workspace_path: str, stack: str) -> dict[str, str]:
    """Build a clean environment that excludes host secrets.

    Only a small allowlist of variables is carried over from the host (the
    ones tooling genuinely needs, e.g. PATH), plus a few sane defaults.
    """
    host = os.environ

    env: dict[str, str] = {
        "PATH": host.get("PATH", ""),
        "HOME": host.get("HOME") or host.get("USERPROFILE", str(Path.home())),
        "PYTHONPATH": workspace_path,
        "NODE_ENV": "test",
        "CI": "true",
        # Make Python output deterministic and unbuffered for cleaner logs.
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    # On Windows several system locations must remain visible for the
    # subprocess loader and toolchains to function at all.
    for key in ("SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "PATHEXT", "WINDIR"):
        if key in host:
            env[key] = host[key]

    if stack == "go":
        # Go needs a cache/home location; reuse host GOPATH if present.
        if "GOPATH" in host:
            env["GOPATH"] = host["GOPATH"]

    return env


async def _run(
    command: str, workspace_path: str, stack: str, timeout: int
) -> CommandResult:
    """Run a shell command in the workspace with a clean env and timeout."""
    # POSIX-style parsing strips quotes correctly into argv on all platforms;
    # test/install commands are simple flag-based commands without backslashes.
    args = shlex.split(command)
    env = _build_env(workspace_path, stack)

    # Resolve the executable on the sandbox PATH. On Windows, npm/npx are .cmd
    # shims that CreateProcess can't launch directly, so route them through
    # cmd.exe. Command strings come from the trusted stack_detector, never the
    # LLM, so this is safe.
    exe = shutil.which(args[0], path=env.get("PATH"))
    if exe is None:
        return CommandResult(
            returncode=127, stdout="",
            stderr=f"executable not found on PATH: {args[0]}", timed_out=False,
        )
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        full_args = [os.environ.get("COMSPEC", "cmd.exe"), "/c", exe, *args[1:]]
    else:
        full_args = [exe, *args[1:]]

    proc = await asyncio.create_subprocess_exec(
        *full_args,
        cwd=workspace_path,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return CommandResult(
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s: {command}",
            timed_out=True,
        )

    return CommandResult(
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        timed_out=False,
    )


async def run_tests(
    workspace_path: str, test_command: str, stack: str
) -> CommandResult:
    """Execute the test suite and capture its output."""
    return await _run(
        test_command, workspace_path, stack, timeout=settings.sandbox_timeout
    )


async def install_dependencies(workspace_path: str, stack: str) -> CommandResult:
    """Install dependencies for the detected stack (120s timeout).

    Returns a success result with empty output when the stack has no install
    step (or is unknown).
    """
    command = _INSTALL_COMMANDS.get(stack)
    if command is None:
        return CommandResult(returncode=0, stdout="", stderr="", timed_out=False)

    return await _run(command, workspace_path, stack, timeout=120)
