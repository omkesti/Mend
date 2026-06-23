import os

from agent.tools.sandbox import _build_env


def test_host_secrets_are_excluded():
    os.environ["GROQ_API_KEY"] = "super-secret-groq"
    os.environ["GITHUB_TOKEN"] = "super-secret-gh"
    env = _build_env(".", "python")
    assert "GROQ_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env


def test_clean_env_sets_ci_flags():
    env = _build_env(".", "python")
    assert env["CI"] == "true"
    assert env["NODE_ENV"] == "test"
    assert "PATH" in env
