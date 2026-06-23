# Mend — CI/CD Healing Agent

An autonomous agent that fixes failing repositories on its own. Give it a GitHub repo URL and it will clone the repo, detect the tech stack, run the test suite, diagnose failures with an LLM, generate and apply code fixes, commit them to a dedicated fix branch, and monitor CI — looping until all tests pass or the retry limit is hit. A React dashboard shows the whole process live.

## How it works

The core is a [LangGraph](https://langchain-ai.github.io/langgraph/) state machine with six nodes and a retry loop:

```
analyze_repo → run_tests → diagnose → generate_fixes → commit_fixes → monitor_ci ─┐
                  ↑                                                                │
                  └──────────────── (CI failed, retries remain) ──────────────────┘
```

- **analyze_repo** — clone the repo, detect the stack, install deps, create a fix branch
- **run_tests** — execute the test suite and capture output
- **diagnose** — LLM turns raw test output into a structured list of failures
- **generate_fixes** — LLM reads each failing file and writes a corrected version
- **commit_fixes** — `git add`, commit (prefixed `[AI-AGENT]`), and push to the fix branch
- **monitor_ci** — poll GitHub Actions and decide whether to loop or stop

The loop ends when CI passes, retries are exhausted, the tests already pass (zero commits), or setup fails (e.g. no test files, unsupported stack) — each surfaced clearly on the dashboard.

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | `llama-3.3-70b-versatile` via the Groq SDK (OpenAI-compatible) |
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
    llm.py           # Groq client + JSON/bug-type helpers
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
  types/             # shared TS types mirroring the API
  lib/               # api.ts (only file that knows the API URL), ws.ts
  store/runStore.ts  # Zustand store
  hooks/useRun.ts    # WS subscription + polling fallback
  components/        # dashboard UI
```

See [`project_context.md`](./project_context.md) for the full architecture, data shapes, and design constraints, and [`CLAUDE.md`](./CLAUDE.md) for contributor guidance.

## Prerequisites

- **Python 3.11+** and **Node.js 18+** (Node 20+ recommended)
- **git** on your `PATH`
- A **Groq API key** — https://console.groq.com/keys
- A **GitHub personal access token** with the `repo` scope (classic PAT, or a fine-grained token granted Contents: Read and write on the target repos). The agent clones and pushes with this token.

## Getting started

### Backend

```bash
cd backend
python -m venv .venv

# activate the venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\Activate.ps1        # Windows PowerShell

pip install -r requirements.txt
cp .env.example .env                # then fill in GROQ_API_KEY and GITHUB_TOKEN
uvicorn main:app --reload           # serves on http://localhost:8000
```

> **Note:** the agent runs each target repo's test command (e.g. `pytest`, `npm test`) as a sandboxed subprocess, resolving the executable from `PATH`. Run `uvicorn` from the **activated venv** so the test runner the target repo installs is reachable. On startup the app creates `WORKSPACE_DIR` and the SQLite database automatically.

### Frontend

```bash
cd frontend
npm install
npm run dev                         # serves on http://localhost:5173
```

Open http://localhost:5173, enter a GitHub repo URL, team name, and leader name, and click **Heal Repository**. The dashboard streams status over WebSocket (with a 3s polling fallback) and shows the run summary, score, CI timeline, and fixes table as they populate. Use **Run history** to revisit past runs.

The frontend talks to the backend at `http://localhost:8000` by default; override with `VITE_API_URL` if the backend runs elsewhere.

### Environment variables (`backend/.env`)

```
GROQ_API_KEY=gsk_...
GITHUB_TOKEN=ghp_...
DATABASE_URL=sqlite+aiosqlite:///./cicd_agent.db
MAX_RETRIES=5
SANDBOX_TIMEOUT=120
WORKSPACE_DIR=/tmp/cicd_agent_workspaces
MODEL=llama-3.3-70b-versatile
```

All settings are read through `backend/config.py` (pydantic-settings); nothing reads `os.environ` directly. `.env` is gitignored — never commit it.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/runs` | Start a run. Body: `{ repo_url, team_name, leader_name }`. Returns `{ run_id, branch_name, status }`. |
| GET | `/api/runs/{run_id}` | Full run detail: run record + all fixes + all CI iterations |
| GET | `/api/runs` | List the last 50 runs (summary) |
| GET | `/api/health` | `{ status: "ok" }` |
| WS | `/ws/{run_id}` | Live `status` / `complete` / `error` events for a run |

Every run also writes a `results.json` to its workspace folder (`{WORKSPACE_DIR}/{run_id}/results.json`).

## Supported stacks

| Stack | Detected by | Default test command |
|---|---|---|
| Python | `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` | `pytest --tb=short -v` (falls back to `unittest`) |
| Node | `package.json` | `scripts.test`, or `npx jest`/`mocha`/`vitest` from deps |
| Go | `go.mod` | `go test ./... -v` |

### Monorepos

Mend detects **every** testable project in a repo, not just one. A repo with a
Python `backend/` and a Node `frontend/` is healed in a single run — each
project's suite is run, diagnosed, and fixed independently, and all fixes land
in one `[AI-AGENT]` commit. An aggregate root manifest (e.g. a root
`requirements.txt` that just re-exports a sub-project) is ignored in favor of
the real sub-project. (This repo is itself a monorepo and heals itself.)

## Running the tests

```bash
cd backend && pytest          # backend unit tests
cd frontend && npm test       # frontend unit tests (vitest)
```

## Scoring

```
base 100
+10 speed bonus when the run finishes under 5 minutes
-2 per commit over 20
final = max(0, base + bonus - penalty)
```

## Known limitations

Built first for personal use, architected to grow later. Deliberate simplifications:

- **No Docker sandbox** — target tests run as a subprocess in the server's environment (process-level isolation, not a container).
- **No job queue** — each run is a background `asyncio` task; concurrent runs share one workspace dir and DB.
- **No auth / multi-tenancy** — single user, local only.
- **SQLite** by default (swap via `DATABASE_URL`; the async layer is already abstracted).
- **GitHub Actions only** for CI — no GitLab CI / CircleCI.
- **No flaky-test detection** — every failure is treated as a real regression.
- **LLM rate limits** — on Groq's free tier, large files or many files in one minute can hit the per-minute token limit; the client backs off and retries, but very large repos may need a paid tier.
