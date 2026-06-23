"""ORM models: AgentRun, FixRecord, CIIteration.

Timestamps are stored as ISO-8601 UTC strings (not native datetimes) to match
the agent's `AgentState`, the WebSocket payloads, and the frontend TypeScript
types, all of which exchange ISO strings.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AgentRun(Base):
    """One row per agent run."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo_url: Mapped[str] = mapped_column(String, nullable=False)
    team_name: Mapped[str] = mapped_column(String, nullable=False)
    leader_name: Mapped[str] = mapped_column(String, nullable=False)
    branch_name: Mapped[str] = mapped_column(String, nullable=False)

    # "pending" | "running" | "passed" | "failed"
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    total_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_fixes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_commits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    base_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speed_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    efficiency_penalty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    fixes: Mapped[list[FixRecord]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="FixRecord.id",
    )
    ci_iterations: Mapped[list[CIIteration]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CIIteration.iteration_number",
    )


class FixRecord(Base):
    """One row per fix attempt within a run."""

    __tablename__ = "fix_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )

    file_path: Mapped[str] = mapped_column(String, nullable=False)
    bug_type: Mapped[str] = mapped_column(String, nullable=False)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_message: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)

    run: Mapped[AgentRun] = relationship(back_populates="fixes")


class CIIteration(Base):
    """One row per loop iteration within a run."""

    __tablename__ = "ci_iterations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )

    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # "passed" | "failed" | "pending" | "no_ci"
    status: Mapped[str] = mapped_column(String, nullable=False)
    failures_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fixes_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[str | None] = mapped_column(String, nullable=True)
    log_summary: Mapped[str | None] = mapped_column(String, nullable=True)

    run: Mapped[AgentRun] = relationship(back_populates="ci_iterations")
