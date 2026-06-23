# Suture — Implementation Task List

Work top to bottom. Don't skip ahead. Each section depends on the one above it.

---

## Phase 0 — Repo setup

- [ ] Create GitHub repo named `suture`
- [ ] Clone locally, open in editor
- [ ] Create root `.gitignore` (Python, Node, `.env`, `__pycache__`, `*.db`, `/tmp`, `node_modules`, `.venv`)
- [ ] Place `CLAUDE.md` at repo root
- [ ] Create `README.md` with one-line description (fill in detail later)
- [ ] Create `backend/` and `frontend/` folders

---

## Phase 1 — Backend foundation

### 1.1 Environment
- [ ] Create `backend/requirements.txt` with all dependencies
- [ ] Create `backend/.env.example` with all required keys and placeholder values
- [ ] Create `backend/.env` (copy from example, fill in real keys — never commit this)
- [ ] Set up Python virtual environment inside `backend/`
- [ ] Run `pip install -r requirements.txt` — verify no errors

### 1.2 Config
- [ ] Create `backend/config.py`
  - [ ] `Settings` class using `pydantic-settings` and `BaseSettings`
  - [ ] Fields: `anthropic_api_key`, `github_token`, `database_url`, `max_retries`, `sandbox_timeout`, `workspace_dir`, `model`
  - [ ] `get_settings()` with `@lru_cache`
  - [ ] All fields read from `.env` — no hardcoded values anywhere

### 1.3 Database
- [ ] Create `backend/database.py`
  - [ ] Async engine from `DATABASE_URL` in settings
  - [ ] `AsyncSessionLocal` session factory
  - [ ] `Base` declarative base
  - [ ] `get_db()` async generator (dependency injection)
  - [ ] `init_db()` that creates all tables on startup

### 1.4 Models
- [ ] Create `backend/models/__init__.py`
- [ ] Create `backend/models/run.py`
  - [ ] `AgentRun` table — all fields from CLAUDE.md
  - [ ] `FixRecord` table — all fields from CLAUDE.md
  - [ ] `CIIteration` table — all fields from CLAUDE.md
  - [ ] Relationships: `AgentRun.fixes`, `AgentRun.ci_iterations` with `cascade="all, delete-orphan"`
  - [ ] Verify all column types match what the frontend expects

---

## Phase 2 — Agent state

- [ ] Create `backend/agent/__init__.py`
- [ ] Create `backend/agent/state.py`
  - [ ] `FailureInfo` TypedDict
  - [ ] `FixInfo` TypedDict
  - [ ] `CIResult` TypedDict
  - [ ] `AgentState` TypedDict — every field from CLAUDE.md
  - [ ] `fixes` and `ci_results` fields use `Annotated[list[...], add]` reducer
  - [ ] Double-check every field name matches what nodes will read/write — this is the contract

---

## Phase 3 — Agent tools

### 3.1 GitHub tool
- [ ] Create `backend/agent/tools/__init__.py`
- [ ] Create `backend/agent/tools/github.py`
  - [ ] `parse_repo_url(url)` → `(owner, repo_name)` tuple
  - [ ] `build_branch_name(team_name, leader_name)` → exact spec format (uppercase, underscores, `_AI_Fix` suffix)
  - [ ] `clone_repo(repo_url, workspace_path)` — inject token into URL, configure git identity
  - [ ] `create_branch(workspace_path, branch_name)` — checkout new branch
  - [ ] `commit_and_push(workspace_path, branch_name, message, repo_url)` — `[AI-AGENT]` prefix, returns `bool` (False if nothing to commit)
  - [ ] `get_ci_status(owner, repo_name, branch_name)` — poll GitHub Actions API, return `"passed" | "failed" | "pending" | "no_ci"`
  - [ ] Handle `GithubException` gracefully — return `"error:{status}"` string, never crash

### 3.2 Sandbox tool
- [ ] Create `backend/agent/tools/sandbox.py`
  - [ ] `run_tests(workspace_path, test_command, stack)` — asyncio subprocess, timeout from settings, return `{ returncode, stdout, stderr, timed_out }`
  - [ ] `_build_env(workspace_path, stack)` — clean env dict (PATH, HOME, PYTHONPATH, NODE_ENV, CI=true), no leaking of host secrets
  - [ ] `install_dependencies(workspace_path, stack)` — detect and run the right install command (pip, npm install, go mod download), 120s timeout

### 3.3 Stack detector
- [ ] Create `backend/agent/tools/stack_detector.py`
  - [ ] `STACK_PROFILES` dict — Python/Node/Go with markers, test patterns, test dirs, commands
  - [ ] `detect_stack(workspace_path)` — return `{ stack, test_command, test_files }`
  - [ ] `_detect_test_command(workspace_path, stack, profile)` — read manifests to pick right runner (pytest vs unittest, jest vs mocha vs vitest)
  - [ ] `_find_test_files(workspace_path, patterns)` — recursive glob, filter out `node_modules/.git/venv/__pycache__/.tox`, return relative paths
  - [ ] Unknown stack: return `stack: "unknown"`, log a warning

---

## Phase 4 — Agent nodes

Create `backend/agent/nodes/__init__.py`

### 4.1 Analyze repo node
- [ ] Create `backend/agent/nodes/analyze.py`
  - [ ] `async def analyze_repo(state: AgentState) -> dict`
  - [ ] Build `workspace_path` from `settings.workspace_dir + run_id`
  - [ ] Call `clone_repo()` → `create_branch()` → `detect_stack()` → `install_dependencies()`
  - [ ] Return: `workspace_path`, `branch_name`, `repo_owner`, `repo_name`, `detected_stack`, `test_command`, `test_files`, `current_iteration: 0`, `all_tests_passing: False`, `should_stop: False`, `error: None`, `started_at` (ISO UTC)
  - [ ] On any exception: return `should_stop: True`, `error: str(e)`

### 4.2 Run tests node
- [ ] Create `backend/agent/nodes/run_tests.py`
  - [ ] `async def run_tests_node(state: AgentState) -> dict`
  - [ ] Call `sandbox.run_tests()`
  - [ ] If `returncode == 0` and not timed out: return `all_tests_passing: True`, `failures: []`
  - [ ] Else: return `raw_test_output: combined stdout+stderr`, `all_tests_passing: False`

### 4.3 Diagnose node
- [ ] Create `backend/agent/nodes/diagnose.py`
  - [ ] `DIAGNOSE_SYSTEM` prompt — JSON-only output, fixed bug type enum, lowercase verb description rule
  - [ ] `async def diagnose_failures(state: AgentState) -> dict`
  - [ ] Truncate `raw_test_output` to 8000 chars (tail, not head — errors are usually at the end)
  - [ ] Call Anthropic SDK with system prompt + raw output
  - [ ] Strip markdown fences from response before `json.loads()`
  - [ ] Validate each item: `bug_type` must be in enum, clamp to `LINTING` if not
  - [ ] On parse error: fallback to one generic `LOGIC` failure entry
  - [ ] Return `{ "failures": [...] }`

### 4.4 Fix node
- [ ] Create `backend/agent/nodes/fix.py`
  - [ ] `FIX_SYSTEM` prompt — JSON-only output with `fixed_content` and `explanation` keys
  - [ ] `async def generate_fixes(state: AgentState) -> dict`
  - [ ] Group failures by `file_path` — one LLM call per file, not per failure
  - [ ] For each file: read current content, build prompt with failures + content, call LLM
  - [ ] Write `fixed_content` back to disk if not None
  - [ ] Build `FixInfo` for each failure with spec-compliant `description` string (`"BUG_TYPE error in path line N → Fix: description"`)
  - [ ] On file not found or LLM error: set `status: "failed"` for that fix, continue
  - [ ] Return `{ "fixes": [...] }` — LangGraph add reducer appends to existing list

### 4.5 Commit node
- [ ] Create `backend/agent/nodes/commit.py`
  - [ ] `async def commit_fixes(state: AgentState) -> dict`
  - [ ] Filter `state["fixes"]` to only `status == "fixed"` ones for this iteration
  - [ ] Build commit message: `f"Iteration {iteration}: fix {n} issue(s) ({types})"`
  - [ ] Call `commit_and_push()` — if nothing to commit (returns False), still record the iteration
  - [ ] Build `CIResult` entry with `status: "pending"` — will be updated by monitor_ci
  - [ ] Return `{ "current_iteration": iteration, "ci_results": [ci_result] }`

### 4.6 Monitor CI node
- [ ] Create `backend/agent/nodes/monitor_ci.py`
  - [ ] `async def monitor_ci(state: AgentState) -> dict`
  - [ ] Poll `get_ci_status()` with exponential-ish backoff: `[5, 10, 15, 20, 30, 30, 30]` seconds
  - [ ] Stop polling when status is `"passed"`, `"failed"`, or `"no_ci"`
  - [ ] Handle `"no_ci"`: use `state["all_tests_passing"]` as ground truth
  - [ ] Set `should_stop = True` if: passed OR `current_iteration >= max_retries` OR error
  - [ ] Return `{ "all_tests_passing", "should_stop" }`

---

## Phase 5 — LangGraph graph

- [ ] Create `backend/agent/graph.py`
  - [ ] `has_failures(state)` routing function — `"passing"` or `"failing"`
  - [ ] `should_stop(state)` routing function — `"end"` or `"loop"`
  - [ ] `build_graph()` — register all 6 nodes, set entry point, wire edges and conditional edges
  - [ ] Edge map: `analyze_repo → run_tests → (failing→diagnose | passing→END) → generate_fixes → commit_fixes → monitor_ci → (loop→run_tests | end→END)`
  - [ ] `agent_graph = build_graph()` — compiled singleton at module level
  - [ ] Smoke test: `agent_graph.get_graph().print_ascii()` to verify topology

---

## Phase 6 — Services layer

### 6.1 Scorer
- [ ] Create `backend/services/scorer.py`
  - [ ] `compute_score(duration_seconds, total_commits) -> dict` — pure function, no IO
  - [ ] Returns `{ base_score, speed_bonus, efficiency_penalty, final_score }`
  - [ ] `final_score` floors at 0

### 6.2 Result builder
- [ ] Create `backend/services/result_builder.py`
  - [ ] `build_results(state, started_at) -> dict` — assembles the full results dict
  - [ ] Calls `compute_score()` internally
  - [ ] `write_results_json(results, workspace_path)` — writes `results.json` to workspace root
  - [ ] Output shape matches `results.json` schema in CLAUDE.md exactly

### 6.3 Runner service
- [ ] Create `backend/services/runner.py`
  - [ ] `async def run_agent(run_id, request, db)` — the only function that calls both the graph and DB
  - [ ] Create initial `AgentRun` DB record with `status: "running"` before graph starts
  - [ ] Broadcast `status` WS event: `"Agent started"`
  - [ ] `await agent_graph.ainvoke(initial_state)`
  - [ ] On success: call `build_results()`, `write_results_json()`, write `FixRecord` and `CIIteration` rows, update `AgentRun`
  - [ ] Broadcast `complete` WS event with full results
  - [ ] On exception: update `AgentRun` to `status: "failed"`, broadcast `error` event

---

## Phase 7 — API layer

### 7.1 WebSocket manager
- [ ] Create `backend/api/ws.py`
  - [ ] `ConnectionManager` class
  - [ ] `active_connections: dict[str, list[WebSocket]]`
  - [ ] `connect(run_id, websocket)`, `disconnect(run_id, websocket)`
  - [ ] `broadcast(run_id, event, data)` — sends `{ "event": "...", "data": {...} }` JSON to all connections for that run_id
  - [ ] Silently ignore send errors (client may have disconnected)
  - [ ] Singleton `manager = ConnectionManager()` at module level

### 7.2 Routes
- [ ] Create `backend/api/routes/__init__.py`
- [ ] Create `backend/api/routes/health.py`
  - [ ] `GET /api/health` → `{ "status": "ok" }`
- [ ] Create `backend/api/routes/runs.py`
  - [ ] `RunRequest` Pydantic schema: `repo_url`, `team_name`, `leader_name`
  - [ ] `POST /api/runs` — generate `run_id`, fire `run_agent()` as `asyncio.create_task()`, return `{ run_id, branch_name, status: "started" }`
  - [ ] `GET /api/runs/{run_id}` — query `AgentRun` + its `fixes` + `ci_iterations`, return full object
  - [ ] `GET /api/runs` — last 50 runs ordered by `started_at DESC`, summary fields only
  - [ ] `WebSocket /ws/{run_id}` — accept, register with manager, keep alive with receive loop, deregister on disconnect

### 7.3 Main app
- [ ] Create `backend/main.py`
  - [ ] `lifespan` context manager: create `workspace_dir`, call `init_db()`
  - [ ] `FastAPI(title="Suture", lifespan=lifespan)`
  - [ ] Add `CORSMiddleware` — allow all origins for local dev
  - [ ] Include routers from `api/routes/runs.py` and `api/routes/health.py`
  - [ ] Smoke test: `uvicorn main:app --reload` → `GET /api/health` returns 200

---

## Phase 8 — Backend integration test

Before touching frontend, verify the full agent loop works end-to-end:

- [ ] Create a test GitHub repo with 2–3 deliberately broken Python files (unused import, syntax error, wrong type)
- [ ] Make sure the repo has no GitHub Actions workflows (to trigger the `no_ci` path first)
- [ ] `POST /api/runs` with the test repo URL
- [ ] Tail the uvicorn logs — watch all 6 nodes execute in sequence
- [ ] `GET /api/runs/{run_id}` — verify fixes, CI iterations, score are all populated
- [ ] Check the test repo on GitHub — verify fix branch was created with `[AI-AGENT]` commits
- [ ] Verify `results.json` was written to the workspace folder
- [ ] Fix any bugs before moving to frontend

---

## Phase 9 — Frontend foundation

### 9.1 Project setup
- [ ] `npm create vite@latest frontend -- --template react-ts` (or scaffold manually)
- [ ] Install dependencies: `zustand`, `recharts`, `@tanstack/react-query`, `tailwindcss`, `autoprefixer`, `postcss`, `clsx`
- [ ] Configure Tailwind: `tailwind.config.js` + `postcss.config.js` + `@tailwind` directives in `index.css`
- [ ] Configure Vite proxy in `vite.config.ts`: `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`
- [ ] Verify `npm run dev` opens without errors

### 9.2 Types
- [ ] Create `src/types/index.ts`
  - [ ] `BugType` union literal type
  - [ ] `RunStatus` union literal type
  - [ ] `FixRecord` interface
  - [ ] `CIIteration` interface
  - [ ] `ScoreBreakdown` interface
  - [ ] `AgentRun` interface (full detail)
  - [ ] `RunListItem` interface (summary)

### 9.3 API client
- [ ] Create `src/lib/api.ts`
  - [ ] `API_BASE` from `import.meta.env.VITE_API_URL` with fallback to `http://localhost:8000`
  - [ ] `startRun(repoUrl, teamName, leaderName) -> Promise<{ run_id, branch_name, status }>`
  - [ ] `getRun(runId) -> Promise<AgentRun>`
  - [ ] `listRuns() -> Promise<RunListItem[]>`
  - [ ] All functions typed with interfaces from `types/index.ts`

### 9.4 WebSocket client
- [ ] Create `src/lib/ws.ts`
  - [ ] `AgentWS` class
  - [ ] Constructor takes `runId` and callbacks: `onStatus`, `onComplete`, `onError`
  - [ ] Connects to `WS_BASE + /ws/${runId}`
  - [ ] Parses `{ event, data }` messages and calls appropriate callback
  - [ ] `disconnect()` method
  - [ ] `isConnected` getter

---

## Phase 10 — Frontend state and data fetching

### 10.1 Zustand store
- [ ] Create `src/store/runStore.ts`
  - [ ] State: `activeRunId`, `activeRun`, `runHistory`, `isLoading`, `_ws` (private)
  - [ ] `startRun(repoUrl, teamName, leaderName)` — call API, set `activeRunId`, connect WS, start polling
  - [ ] `loadRun(runId)` — call API, set `activeRun`
  - [ ] `loadHistory()` — call API, set `runHistory`
  - [ ] `_connectWs(runId)` — create `AgentWS`, wire callbacks to update store
  - [ ] `_disconnectWs()` — close connection
  - [ ] WS `onComplete` callback: set `activeRun`, call `_disconnectWs()`
  - [ ] WS `onError` callback: set error on `activeRun`

### 10.2 useRun hook
- [ ] Create `src/hooks/useRun.ts`
  - [ ] Takes `runId: string | null`
  - [ ] Polls `getRun(runId)` every 3 seconds via `setInterval` as a fallback
  - [ ] Stops polling when `status` is `"passed"` or `"failed"`
  - [ ] Updates store with polled data
  - [ ] Returns current `activeRun` from store

---

## Phase 11 — Frontend components

Build in this order — each component is independently testable with hardcoded props before wiring to the store.

- [ ] **`StatusBadge.tsx`** — props: `status: RunStatus`. Four color variants. No logic.

- [ ] **`InputSection.tsx`**
  - [ ] Three controlled inputs: `repoUrl`, `teamName`, `leaderName`
  - [ ] Validate before submitting: all required, must contain `github.com`
  - [ ] Calls `runStore.startRun()` on submit
  - [ ] Disable all inputs + show "AGENT RUNNING..." while `isLoading` or `status === "running"`

- [ ] **`RunSummaryCard.tsx`**
  - [ ] Props: `run: AgentRun`
  - [ ] Display: repo URL, team, leader, branch name, failures detected, fixes applied, commits, duration, `StatusBadge`
  - [ ] Show live pulse animation when `status === "running"`

- [ ] **`ScoreBreakdown.tsx`**
  - [ ] Props: `score: ScoreBreakdown`, `status: RunStatus`
  - [ ] Big number display for `final_score`
  - [ ] Three labeled lines: base, speed bonus, efficiency penalty
  - [ ] Recharts `BarChart` with 4 bars: Base / +Speed / -Penalty / Total, each a different color

- [ ] **`CICDTimeline.tsx`**
  - [ ] Props: `iterations: CIIteration[]`, `maxRetries: number`, `status: RunStatus`
  - [ ] One row per iteration: pass/fail dot, iteration number, timestamp, summary text, failures/fixes count
  - [ ] Render empty placeholder rows for remaining iterations up to `maxRetries`
  - [ ] Show pending pulse on last row if `status === "running"`

- [ ] **`FixesTable.tsx`**
  - [ ] Props: `fixes: FixRecord[]`
  - [ ] Columns: File | Bug Type | Line | Description | Status
  - [ ] Color-coded bug type badge (6 distinct colors, one per type)
  - [ ] ✓ Fixed (green) / ✗ Failed (red) in status column

- [ ] **`RunHistory.tsx`**
  - [ ] On mount: call `runStore.loadHistory()`
  - [ ] List of runs: repo name (trimmed URL), team, status badge, final score
  - [ ] Click row: call `runStore.loadRun(id)`, navigate back to main view
  - [ ] Empty state message if no runs

---

## Phase 12 — Wire everything together

- [ ] Create `src/App.tsx`
  - [ ] `showHistory` boolean toggle state
  - [ ] Render `InputSection` always
  - [ ] Render loading state when `isLoading && !activeRun`
  - [ ] Render `RunSummaryCard`, `ScoreBreakdown`, `CICDTimeline`, `FixesTable` when `activeRun` exists
  - [ ] Show error banner if `activeRun.error_message`
  - [ ] "Run history" toggle in header
  - [ ] `useRun(activeRunId)` at top level to start polling

- [ ] **Full end-to-end test:**
  - [ ] Start backend: `uvicorn main:app --reload`
  - [ ] Start frontend: `npm run dev`
  - [ ] Open `http://localhost:5173`
  - [ ] Submit the same broken test repo from Phase 8
  - [ ] Watch live updates appear on dashboard
  - [ ] Verify score panel, fixes table, and CI timeline all populate correctly
  - [ ] Click "run history", verify the run appears, click it to reload

---

## Phase 13 — Polish and edge cases

- [ ] Test with a repo that has **no test files** — should stop gracefully with a clear message
- [ ] Test with an **invalid GitHub URL** — frontend validates, backend handles 404 from PyGithub
- [ ] Test with a **private repo** — verify token scopes are sufficient
- [ ] Test with a **Node.js repo** — verify stack detection and npm install work
- [ ] Test with a repo where **all tests already pass** — agent should stop after step 2 with zero commits
- [ ] Test with a repo that has **GitHub Actions** configured — verify CI polling works
- [ ] Handle `SANDBOX_TIMEOUT` — show meaningful error in dashboard, not a crash
- [ ] Verify `results.json` is written correctly after every run type (pass, fail, error)
- [ ] Verify run history persists across server restarts (SQLite file survives)
- [ ] Test the `no_ci` edge case — repo with no Actions workflows

---

## Phase 14 — Final cleanup

- [ ] Fill in `README.md` fully: what it does, setup steps, env vars, how to run, known limitations
- [ ] Add `.gitignore` entries: `.env`, `*.db`, `/tmp`, `__pycache__`, `.venv`, `node_modules`, `dist`
- [ ] Confirm `.env` is NOT committed (check `git status`)
- [ ] Remove any debug `print()` statements left in agent nodes
- [ ] Verify `CLAUDE.md` at root is accurate and up to date
- [ ] Do one clean run on a fresh clone to verify setup instructions in README work

---

## Summary — what you're building in order

```
Phase 0   → Repo skeleton
Phase 1   → Backend config + DB
Phase 2   → AgentState (the contract everything talks through)
Phase 3   → Tools (GitHub, sandbox, stack detector)
Phase 4   → Nodes (the 6 agent steps)
Phase 5   → LangGraph graph (wires the nodes)
Phase 6   → Services (scorer, result builder, runner)
Phase 7   → FastAPI API (routes + WebSocket)
Phase 8   → Backend integration test ← don't skip this
Phase 9   → Frontend setup + types + API client
Phase 10  → Store + hook
Phase 11  → Components (one at a time)
Phase 12  → Wire + full E2E test
Phase 13  → Edge cases
Phase 14  → Cleanup
```
