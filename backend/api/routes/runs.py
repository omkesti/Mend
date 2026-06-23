"""Run routes: start a run, fetch one, list recent, and the live WS stream."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent.tools.github import build_branch_name
from api.ws import manager
from database import AsyncSessionLocal, get_db
from models.run import AgentRun, CIIteration, FixRecord
from services.runner import run_agent

logger = logging.getLogger(__name__)

router = APIRouter()


class RunRequest(BaseModel):
    repo_url: str
    team_name: str
    leader_name: str


# --- serialization helpers -------------------------------------------------

def _fix_dict(f: FixRecord) -> dict:
    return {
        "id": f.id,
        "file_path": f.file_path,
        "bug_type": f.bug_type,
        "line_number": f.line_number,
        "commit_message": f.commit_message,
        "status": f.status,
        "description": f.description,
        "created_at": f.created_at,
    }


def _ci_dict(c: CIIteration) -> dict:
    return {
        "id": c.id,
        "iteration_number": c.iteration_number,
        "status": c.status,
        "failures_found": c.failures_found,
        "fixes_applied": c.fixes_applied,
        "timestamp": c.timestamp,
        "log_summary": c.log_summary,
    }


def _run_summary(r: AgentRun) -> dict:
    return {
        "id": r.id,
        "repo_url": r.repo_url,
        "team_name": r.team_name,
        "leader_name": r.leader_name,
        "branch_name": r.branch_name,
        "status": r.status,
        "total_failures": r.total_failures,
        "total_fixes": r.total_fixes,
        "total_commits": r.total_commits,
        "final_score": r.final_score,
        "duration_seconds": r.duration_seconds,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
    }


def _run_detail(r: AgentRun) -> dict:
    return {
        **_run_summary(r),
        "base_score": r.base_score,
        "speed_bonus": r.speed_bonus,
        "efficiency_penalty": r.efficiency_penalty,
        "error_message": r.error_message,
        "fixes": [_fix_dict(f) for f in r.fixes],
        "ci_iterations": [_ci_dict(c) for c in r.ci_iterations],
    }


# --- background driver -----------------------------------------------------

async def _run_in_background(run_id: str, payload: RunRequest) -> None:
    """Own a fresh DB session for the life of the agent run.

    The request-scoped session closes when POST returns, so the background task
    must not reuse it.
    """
    async with AsyncSessionLocal() as db:
        await run_agent(run_id, payload, db)


# --- routes ----------------------------------------------------------------

@router.post("/api/runs")
async def create_run(request: RunRequest) -> dict:
    run_id = str(uuid.uuid4())
    branch_name = build_branch_name(request.team_name, request.leader_name)
    asyncio.create_task(_run_in_background(run_id, request))
    return {"run_id": run_id, "branch_name": branch_name, "status": "started"}


@router.get("/api/runs/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.fixes),
            selectinload(AgentRun.ci_iterations),
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_detail(run)


@router.get("/api/runs")
async def list_runs(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(
        select(AgentRun).order_by(AgentRun.started_at.desc()).limit(50)
    )
    return [_run_summary(r) for r in result.scalars().all()]


@router.websocket("/ws/{run_id}")
async def run_ws(websocket: WebSocket, run_id: str) -> None:
    await manager.connect(run_id, websocket)
    try:
        while True:
            # Keep the connection open; clients aren't expected to send data.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(run_id, websocket)
