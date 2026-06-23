# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo is currently **pre-implementation**. The only artifact is `project_context.md`, the full design spec. Treat it as the source of truth: it defines the target file layout, the agent graph, the data shapes, and every hard constraint below. When building, follow the recommended build order in `project_context.md` (backend bottom-up, then frontend) and the planned layout under `backend/` and `frontend/` (not yet created).

## What this is

An autonomous CI/CD healing agent: takes a GitHub repo URL, clones it, detects the stack, runs tests, uses Claude to diagnose failures and generate fixes, commits to a fix branch, monitors GitHub Actions CI, and loops until tests pass or `max_retries` is hit. A React dashboard streams progress live over WebSocket.

## Tech stack

- **Backend**: FastAPI + uvicorn (async), LangGraph agent, Anthropic SDK (`claude-sonnet-4-6`), SQLAlchemy async + aiosqlite, PyGithub + GitPython.
- **Frontend**: React 18 + Vite + TypeScript, Tailwind, Zustand, TanStack Query, Recharts.

## Commands

No build tooling exists yet. Once scaffolded, the intended commands are:

```bash
# Backend (from backend/)
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (from frontend/)
npm install
npm run dev
```

There is no test/lint setup in the spec — add one when scaffolding and update this section.

## Architecture: three isolated layers

The defining property of this codebase is strict separation of concerns. Violating these boundaries is the most likely way to break the design:

| Layer | May touch | Must NOT touch |
|---|---|---|
| `backend/agent/` | `AgentState`, tools, Anthropic SDK | FastAPI, SQLAlchemy, WebSocket |
| `backend/api/` | FastAPI, WebSocket manager, route schemas | LangGraph, SQLAlchemy directly |
| `backend/services/` | agent graph **and** DB session (the only glue layer) | HTTP request/response objects |
| `backend/models/` | SQLAlchemy only | everything else |
| `frontend/lib/api.ts` | `fetch`, `VITE_API_URL` | store, components |
| `frontend/store/` | `lib/api.ts`, `lib/ws.ts` | direct fetch, DB |
| `frontend/components/` | store, hooks | `lib/api.ts` directly, store internals |

The agent in `backend/agent/` knows nothing about HTTP, the DB, or WebSockets. `services/runner.py` is the **only** place that wires the agent graph to the DB and broadcasts WebSocket events.

## The agent loop (LangGraph StateGraph)

Six nodes with a conditional retry loop, in `backend/agent/`:

```
analyze_repo → run_tests → diagnose → generate_fixes → commit_fixes → monitor_ci ─┐
                  ↑                                                                │
                  └──────────────── (CI failed, retries remain) ──────────────────┘
```

Routing: after `run_tests`, if `all_tests_passing` → END, else → `diagnose`. After `monitor_ci`, if `should_stop` (passed OR retries exhausted OR error) → END, else → `run_tests`.

- `AgentState` (TypedDict in `agent/state.py`) is the single source of truth. **Define it completely before writing any node.**
- Every node signature is `async def node(state: AgentState) -> dict` and returns **only the keys that changed**.
- `fixes` and `ci_results` use LangGraph `Annotated[list, add]` reducers — they accumulate across iterations; do not overwrite them.

## Hard constraints — never deviate

- **Bug type enum** (exact, everywhere — prompts, DB, TS types, badges): `LINTING | SYNTAX | LOGIC | TYPE_ERROR | IMPORT | INDENTATION`. If the LLM emits anything else, clamp to `LINTING`.
- **Branch naming** (`agent/tools/github.py` → `build_branch_name`): `f"{TEAM_NAME}_{LEADER_NAME}_AI_Fix"` where each part is `.upper().replace(" ", "_")`.
- **Commit messages**: always prefixed `[AI-AGENT]`. **Never push to `main`** — always push to the generated fix branch.
- **Config access**: all env vars go through `backend/config.py` (pydantic-settings). Never read `os.environ` directly anywhere else.
- **Frontend API access**: `lib/api.ts` is the only file that knows `VITE_API_URL`; components never call raw `fetch`.

## LLM prompt rules

- Diagnose and fix nodes must instruct the model to output **only** valid JSON (no markdown, no preamble); strip accidental code fences before `json.loads()`.
- On any parse failure, **never crash the loop**: diagnose falls back to a single generic `LOGIC` entry; fix marks that file's fix `status: "failed"` and continues.
- Fix node sends the **entire** current file content, and groups all failures in one file into a single LLM call (not one call per failure).
- **Never send secrets to the LLM** — strip API-key/token/`.env`-pattern values from file content before it enters a prompt.

## Important edge case: "no CI"

When `monitor_ci` finds zero GitHub Actions runs on the branch, treat the latest `run_tests` result as ground truth (`all_tests_passing` → `"passed"`/`"failed"`) and set the record's `status = "no_ci"` so the dashboard reflects it.

## Scoring (`backend/services/scorer.py`, pure functions)

```
base_score = 100
speed_bonus = 10 if duration_seconds < 300 else 0
efficiency_penalty = max(0, total_commits - 20) * 2
final_score = max(0, base_score + speed_bonus - efficiency_penalty)
```

## Known simplifications (intentional, personal-use scope)

No Docker sandbox (tests run via `asyncio` subprocess in the server's env), no job queue (agent runs as a background `asyncio.create_task()`), no auth/multi-tenancy, SQLite (swap via `DATABASE_URL`), GitHub Actions only, no flaky-test detection. Don't "fix" these unless asked — they're deliberate.
