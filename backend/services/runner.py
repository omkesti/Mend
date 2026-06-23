"""Runner service: the single place that drives the agent graph AND the DB.

`run_agent` creates the AgentRun record, invokes the compiled graph, persists
the fixes/iterations/score, writes results.json, and broadcasts WebSocket
events at each lifecycle stage. Everything DB- and WS-related lives here so the
agent and API layers stay isolated.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from agent.graph import agent_graph
from agent.state import AgentState
from agent.tools import github
from api import ws
from config import get_settings
from models.run import AgentRun, CIIteration, FixRecord
from services.result_builder import build_results, write_results_json

logger = logging.getLogger(__name__)
settings = get_settings()


def _initial_state(run_id: str, repo_url: str, team_name: str,
                   leader_name: str, branch_name: str) -> AgentState:
    return {
        "run_id": run_id,
        "repo_url": repo_url,
        "team_name": team_name,
        "leader_name": leader_name,
        "branch_name": branch_name,
        "max_retries": settings.max_retries,
        # Reducer-backed accumulators must start as empty lists.
        "fixes": [],
        "ci_results": [],
    }  # type: ignore[return-value]


async def run_agent(run_id: str, request, db: AsyncSession) -> None:
    """Execute one full agent run, persisting and broadcasting throughout."""
    repo_url = request.repo_url
    team_name = request.team_name
    leader_name = request.leader_name
    branch_name = github.build_branch_name(team_name, leader_name)
    started_at = datetime.now(timezone.utc).isoformat()

    run = AgentRun(
        id=run_id,
        repo_url=repo_url,
        team_name=team_name,
        leader_name=leader_name,
        branch_name=branch_name,
        status="running",
        started_at=started_at,
    )
    db.add(run)
    await db.commit()

    await ws.broadcast(run_id, "status", {"status": "running", "message": "Agent started"})

    try:
        final_state = await agent_graph.ainvoke(
            _initial_state(run_id, repo_url, team_name, leader_name, branch_name)
        )

        results = build_results(final_state, started_at)
        write_results_json(results, final_state.get("workspace_path", ""))

        # Persist per-fix and per-iteration rows.
        for f in final_state.get("fixes", []):
            db.add(FixRecord(
                run_id=run_id,
                file_path=f["file_path"],
                bug_type=f["bug_type"],
                line_number=f.get("line_number"),
                commit_message=f["commit_message"],
                status=f["status"],
                description=f["description"],
                created_at=datetime.now(timezone.utc).isoformat(),
            ))
        for cr in results["ci_timeline"]:
            db.add(CIIteration(
                run_id=run_id,
                iteration_number=cr["iteration"],
                status=cr["status"],
                failures_found=cr["failures_found"],
                fixes_applied=cr["fixes_applied"],
                timestamp=cr["timestamp"],
                log_summary=cr["log_summary"],
            ))

        # Update the run summary from the assembled results.
        score = results["score"]
        run.status = results["status"]
        run.total_failures = results["total_failures"]
        run.total_fixes = results["total_fixes_applied"]
        run.total_commits = results["total_commits"]
        run.base_score = score["base_score"]
        run.speed_bonus = score["speed_bonus"]
        run.efficiency_penalty = score["efficiency_penalty"]
        run.final_score = score["final_score"]
        run.duration_seconds = results["duration_seconds"]
        run.finished_at = results["finished_at"]
        run.error_message = results["error"]
        await db.commit()

        await ws.broadcast(run_id, "complete", results)
        logger.info("run %s finished with status %s", run_id, run.status)
    except Exception as exc:  # noqa: BLE001 — surface any failure to the dashboard
        logger.exception("run %s failed", run_id)
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc).isoformat()
        await db.commit()
        await ws.broadcast(run_id, "error", {"message": str(exc)})
