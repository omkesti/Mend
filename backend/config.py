"""Application configuration.

All environment access for the backend funnels through here. No other module
should read `os.environ` directly — import `get_settings()` instead.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from `backend/.env`."""

    groq_api_key: str
    github_token: str
    database_url: str = "sqlite+aiosqlite:///./cicd_agent.db"
    max_retries: int = 5
    sandbox_timeout: int = 120
    workspace_dir: str = "/tmp/cicd_agent_workspaces"
    model: str = "llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=(),
    )


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
