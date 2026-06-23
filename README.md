# Mend — CI/CD Healing Agent

An autonomous agent that fixes failing repositories on its own. Give it a GitHub repo URL and it will clone the repo, detect the tech stack, run the test suite, diagnose failures with an LLM, generate and apply code fixes, commit them to a dedicated fix branch, and monitor CI — looping until all tests pass or the retry limit is hit. A React dashboard shows the whole process live.

> **Status:** pre-implementation. This repository currently contains the design specification ([`project_context.md`](./project_context.md)) and guidance for contributors ([`CLAUDE.md`](./CLAUDE.md)). The code described below is the intended target layout.

## How it works

The core is a [LangGraph](https://langchain-ai.github.io/langgraph/) state machine with six nodes and a retry loop:

```
analyze_repo → run_tests → diagnose → generate_fixes → commit_fixes → monitor_ci ─┐
                  ↑                                                                │
                  └──────────────── (CI failed, retries remain) ──────────────────┘
```

- **analyze_repo** — clone the repo, detect the stack, create a fix branch
- **run_tests** — execute the test suite and capture output
- **diagnose** — LLM turns raw test output into a structured list of failures
- **generate_fixes** — LLM reads each failing file and writes a corrected version
- **commit_fixes** — `git add`, commit (prefixed `[AI-AGENT]`), and push to the fix branch
- **monitor_ci** — poll GitHub Actions and decide whether to loop or stop

The loop ends when CI passes, retries are exhausted, or an error occurs.

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Claude (`claude-sonnet-4-6`) via the Anthropic SDK |
| Backend API | FastAPI + uvicorn (async) |
| Realtime | FastAPI native WebSocket |
| Database | SQLite via SQLAlchemy async + aiosqlite |
| GitHub integration | PyGithub + GitPython |
| Frontend | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS |
| State / data | Zustand + TanStack Query |
| Charts | Recharts |

## Project layout

```
backend/
  main.py            # FastAPI app, lifespan, CORS, routes
  config.py          # pydantic-settings — all env vars
  database.py        # async engine, session factory, init_db()
  agent/             # LangGraph — no knowledge of HTTP or DB
    state.py         # AgentState (single source of truth)
    graph.py         # compiled StateGraph
    nodes/           # analyze, run_tests, diagnose, fix, commit, monitor_ci
    tools/           # github, sandbox, stack_detector
  api/               # FastAPI layer — no knowledge of LangGraph
    ws.py            # WebSocket manager
    routes/          # runs, health
  models/run.py      # SQLAlchemy ORM: AgentRun, FixRecord, CIIteration
  services/          # the only glue between agent + DB
    runner.py        # start agent, write DB, broadcast WS events
    scorer.py        # scoring (pure functions)
    result_builder.py

frontend/src/
  lib/               # api.ts (only file that knows the API URL), ws.ts
  store/runStore.ts  # Zustand store
  hooks/useRun.ts    # WS subscription + polling fallback
  components/        # dashboard UI
```

See [`project_context.md`](./project_context.md) for the full architecture, data shapes, and design constraints.

## Getting started

> The scaffold does not exist yet. These are the intended setup steps.

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment variables (`backend/.env`)

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
DATABASE_URL=sqlite+aiosqlite:///./cicd_agent.db
MAX_RETRIES=5
SANDBOX_TIMEOUT=120
WORKSPACE_DIR=/tmp/cicd_agent_workspaces
MODEL=claude-sonnet-4-6
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/runs` | Start a run. Body: `{ repo_url, team_name, leader_name }`. Returns `{ run_id, branch_name, status }`. |
| GET | `/api/runs/{run_id}` | Full run detail: run record + all fixes + all CI iterations |
| GET | `/api/runs` | List the last 50 runs (summary) |
| GET | `/api/health` | `{ status: "ok" }` |
| WS | `/ws/{run_id}` | Live `status` / `complete` / `error` events for a run |

## Supported stacks

| Stack | Detected by | Default test command |
|---|---|---|
| Python | `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` | `pytest --tb=short -v` |
| Node | `package.json` | `scripts.test`, or jest/mocha/vitest from devDependencies |
| Go | `go.mod` | `go test ./... -v` |

## Scope and limitations

Built first for personal use, architected to grow later. Current deliberate simplifications: no Docker sandbox (tests run in a subprocess), no job queue (runs as a background task), no auth or multi-tenancy, SQLite by default, GitHub Actions only, and no flaky-test detection.
