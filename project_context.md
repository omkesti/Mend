# CI/CD Healing Agent — Project Context for Claude Code

## What this project is

An autonomous agent that takes a GitHub repository URL, clones it, detects the tech stack, runs the test suite, diagnoses failures using an LLM, generates and applies code fixes, commits them to a new branch, and monitors CI — looping until all tests pass or the retry limit is hit. A React dashboard shows everything live.

Built first for personal use. Architected to scale into a startup product later.

---

## Tech stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Claude Sonnet (`claude-sonnet-4-6`) via Anthropic SDK |
| Backend API | FastAPI + uvicorn (async) |
| WebSocket | FastAPI native WebSocket |
| Database | SQLite via SQLAlchemy async + aiosqlite (dev) |
| GitHub integration | PyGithub + GitPython |
| Sandboxed execution | asyncio subprocess with timeout |
| Frontend | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS |
| State management | Zustand |
| Data fetching | TanStack Query |
| Charts | Recharts |
| Stack detection | Custom file-system heuristics (no hardcoded paths) |

---

## Repo structure

```
cicd-healing-agent/
├── README.md
├── .env.example
├── .gitignore
│
├── backend/
│   ├── main.py                        # FastAPI app, lifespan, CORS, route registration
│   ├── config.py                      # pydantic-settings: all env vars in one place
│   ├── database.py                    # async engine, session factory, Base, init_db()
│   ├── requirements.txt
│   ├── .env                           # gitignored
│   │
│   ├── agent/                         # LangGraph — knows nothing about HTTP or DB
│   │   ├── state.py                   # AgentState TypedDict — shared across all nodes
│   │   ├── graph.py                   # compiled LangGraph StateGraph
│   │   ├── nodes/
│   │   │   ├── analyze.py             # clone repo, detect stack, create branch
│   │   │   ├── run_tests.py           # execute test suite, capture output
│   │   │   ├── diagnose.py            # LLM: raw output → structured FailureInfo list
│   │   │   ├── fix.py                 # LLM: read file + failure → write corrected file
│   │   │   ├── commit.py              # git add, [AI-AGENT] commit, push
│   │   │   └── monitor_ci.py          # poll GitHub Actions, decide loop/stop
│   │   └── tools/
│   │       ├── github.py              # clone, branch, commit, push, CI poll, branch naming
│   │       ├── sandbox.py             # run subprocess with timeout + clean env
│   │       └── stack_detector.py      # detect Python/Node/Go from manifests, find test files
│   │
│   ├── api/                           # FastAPI layer — knows nothing about LangGraph
│   │   ├── ws.py                      # WebSocket connection manager, broadcast helper
│   │   └── routes/
│   │       ├── runs.py                # POST /api/runs, GET /api/runs/{id}, GET /api/runs
│   │       └── health.py              # GET /api/health
│   │
│   ├── models/
│   │   └── run.py                     # SQLAlchemy ORM: AgentRun, FixRecord, CIIteration
│   │
│   └── services/                      # glue layer — only place that touches both agent + DB
│       ├── runner.py                  # start agent, handle DB writes, broadcast WS events
│       ├── scorer.py                  # pure functions: compute base/bonus/penalty/final score
│       └── result_builder.py          # assemble final results dict, write results.json
│
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.js
    ├── postcss.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── index.css
        ├── types/
        │   └── index.ts               # all shared TypeScript types (AgentRun, FixRecord, etc.)
        ├── lib/
        │   ├── api.ts                 # typed fetch wrappers — only file that knows API_BASE_URL
        │   └── ws.ts                  # WebSocket client class
        ├── store/
        │   └── runStore.ts            # Zustand store: active run, history, startRun(), loadRun()
        ├── hooks/
        │   └── useRun.ts              # WS subscribe + polling fallback for a given run ID
        └── components/
            ├── InputSection.tsx       # repo URL + team name + leader name + run button
            ├── RunSummaryCard.tsx     # repo, branch, failures, fixes, duration, status badge
            ├── ScoreBreakdown.tsx     # base/bonus/penalty chart (Recharts BarChart)
            ├── FixesTable.tsx         # table: file | bug type | line | description | status
            ├── CICDTimeline.tsx       # per-iteration pass/fail strip with timestamps
            ├── StatusBadge.tsx        # reusable PASSED/FAILED/RUNNING/PENDING badge
            └── RunHistory.tsx         # list of past runs, click to reload
```

---

## The agent loop

The agent is a LangGraph `StateGraph` with 6 nodes and a conditional retry loop. It runs entirely in `backend/agent/` and has zero knowledge of FastAPI, the database, or WebSockets.

```
analyze_repo
    ↓
run_tests ←──────────────────────────────────────────┐
    ↓ (failures exist)                               │
diagnose                                         (retry, iteration < max_retries)
    ↓                                                │
generate_fixes                                       │
    ↓                                                │
commit_fixes                                         │
    ↓                                                │
monitor_ci ──(CI failed, retries remain)─────────────┘
    ↓
   END  (CI passed OR retries exhausted OR error)
```

**Routing logic:**
- After `run_tests`: if `all_tests_passing == True` → END. Else → `diagnose`.
- After `monitor_ci`: if `should_stop == True` (passed OR exhausted OR error) → END. Else → `run_tests`.

**What each node does:**

| Node | Reads from state | Writes to state |
|---|---|---|
| `analyze_repo` | `repo_url`, `team_name`, `leader_name` | `workspace_path`, `branch_name`, `detected_stack`, `test_command`, `test_files` |
| `run_tests` | `workspace_path`, `test_command`, `detected_stack` | `raw_test_output`, `all_tests_passing` |
| `diagnose` | `raw_test_output` | `failures` (list of FailureInfo) |
| `generate_fixes` | `failures`, `workspace_path` | `fixes` (appends FixInfo per failure) |
| `commit_fixes` | `workspace_path`, `branch_name`, `repo_url`, `fixes` | `current_iteration`, `ci_results` (appends one CIResult) |
| `monitor_ci` | `repo_owner`, `repo_name`, `branch_name`, `current_iteration`, `max_retries` | `all_tests_passing`, `should_stop` |

---

## AgentState — the single source of truth

Defined in `backend/agent/state.py`. Every node function signature is `async def node_name(state: AgentState) -> dict` — return only the keys that changed.

```python
class AgentState(TypedDict):
    # Input (set before graph starts)
    run_id: str
    repo_url: str
    team_name: str
    leader_name: str
    branch_name: str
    max_retries: int

    # Set by analyze_repo
    workspace_path: str
    repo_owner: str
    repo_name: str
    detected_stack: str            # "python" | "node" | "go" | "unknown"
    test_command: str
    test_files: list[str]

    # Set by run_tests
    raw_test_output: str

    # Set by diagnose
    failures: list[FailureInfo]

    # Accumulated across all iterations (LangGraph Annotated add reducer)
    fixes: Annotated[list[FixInfo], add]
    ci_results: Annotated[list[CIResult], add]

    # Loop control
    current_iteration: int
    all_tests_passing: bool
    should_stop: bool
    error: str | None

    # Timing
    started_at: str                # ISO format UTC
```

**FailureInfo:**
```python
class FailureInfo(TypedDict):
    file_path: str
    bug_type: str       # must be one of the 6 valid types (see below)
    line_number: int | None
    description: str    # starts with a lowercase verb: "remove the unused import"
    raw_output: str     # the relevant snippet from test output
```

**FixInfo:**
```python
class FixInfo(TypedDict):
    file_path: str
    bug_type: str
    line_number: int | None
    commit_message: str   # e.g. "Fix LINTING in src/utils.py line 15"
    description: str      # e.g. "LINTING error in src/utils.py line 15 → Fix: remove the unused import"
    status: str           # "fixed" | "failed"
    patch: str | None     # LLM explanation of what changed
```

**CIResult:**
```python
class CIResult(TypedDict):
    iteration: int
    status: str           # "passed" | "failed" | "pending" | "no_ci"
    failures_found: int
    fixes_applied: int
    timestamp: str        # ISO format UTC
    log_summary: str
```

---

## Valid bug types — exact enum, never deviate

```
LINTING | SYNTAX | LOGIC | TYPE_ERROR | IMPORT | INDENTATION
```

These must appear exactly in this form everywhere: LLM prompts, DB records, frontend badge labels, TypeScript types. If the LLM outputs anything outside this set, clamp it to `LINTING` as the fallback.

---

## Branch naming — hard constraint

Function lives in `backend/agent/tools/github.py`:

```python
def build_branch_name(team_name: str, leader_name: str) -> str:
    def sanitize(s: str) -> str:
        return s.upper().replace(" ", "_")
    return f"{sanitize(team_name)}_{sanitize(leader_name)}_AI_Fix"
```

Examples:
- `"RIFT ORGANISERS"` + `"Saiyam Kumar"` → `RIFT_ORGANISERS_SAIYAM_KUMAR_AI_Fix`
- `"Code Warriors"` + `"John Doe"` → `CODE_WARRIORS_JOHN_DOE_AI_Fix`

---

## Commit message format — hard constraint

Every commit must be prefixed with `[AI-AGENT]`:

```
[AI-AGENT] Fix LINTING in src/utils.py line 15
[AI-AGENT] Iteration 2: fix 3 issue(s) (SYNTAX, IMPORT)
```

Never push directly to `main`. Always push to the generated fix branch.

---

## DB models — defined in `backend/models/run.py`

**AgentRun** — one row per agent run
```
id (str PK), repo_url, team_name, leader_name, branch_name,
status ("pending"|"running"|"passed"|"failed"),
total_failures, total_fixes, total_commits,
base_score, speed_bonus, efficiency_penalty, final_score,
duration_seconds, started_at, finished_at, error_message
```

**FixRecord** — one row per fix attempt
```
id (int PK autoincrement), run_id (FK → AgentRun),
file_path, bug_type, line_number, commit_message, status, description, created_at
```

**CIIteration** — one row per loop iteration
```
id (int PK autoincrement), run_id (FK → AgentRun),
iteration_number, status, failures_found, fixes_applied, timestamp, log_summary
```

---

## Scoring logic — in `backend/services/scorer.py`

```python
base_score = 100
speed_bonus = 10 if duration_seconds < 300 else 0    # under 5 minutes
efficiency_penalty = max(0, total_commits - 20) * 2  # -2 per commit over 20
final_score = max(0, base_score + speed_bonus - efficiency_penalty)
```

---

## API surface

**REST — defined in `backend/api/routes/`**

| Method | Path | Description |
|---|---|---|
| POST | `/api/runs` | Start a new agent run. Body: `{ repo_url, team_name, leader_name }`. Returns `{ run_id, branch_name, status }`. Fires agent as a background task. |
| GET | `/api/runs/{run_id}` | Full run detail: run record + all fixes + all CI iterations |
| GET | `/api/runs` | List of last 50 runs (summary only) |
| GET | `/api/health` | `{ status: "ok" }` |

**WebSocket — defined in `backend/api/ws.py`**

Client connects to `/ws/{run_id}` immediately after POST /api/runs.

Events the server sends:
```json
{ "event": "status",   "data": { "status": "running", "message": "..." } }
{ "event": "complete", "data": { ...full run object... } }
{ "event": "error",    "data": { "message": "..." } }
```

---

## Stack detection logic — `backend/agent/tools/stack_detector.py`

Detection is manifest-first, never hardcoded test paths:

| Stack | Detected by | Default test command |
|---|---|---|
| Python | `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` | `pytest --tb=short -v` |
| Node | `package.json` | Read `scripts.test` or detect jest/mocha/vitest from devDependencies |
| Go | `go.mod` | `go test ./... -v` |
| Unknown | fallback | log warning, set `should_stop: True` |

Test file discovery uses glob patterns recursively, excluding `node_modules`, `.git`, `venv`, `__pycache__`, `.tox`.

---

## Environment variables — `backend/.env`

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
DATABASE_URL=sqlite+aiosqlite:///./cicd_agent.db
MAX_RETRIES=5
SANDBOX_TIMEOUT=120
WORKSPACE_DIR=/tmp/cicd_agent_workspaces
MODEL=claude-sonnet-4-6
```

All accessed via `backend/config.py` using `pydantic-settings`. Never import `os.environ` directly anywhere else.

---

## LLM prompt conventions

**Diagnose node prompt rules:**
- System prompt instructs: output ONLY valid JSON array, no markdown, no preamble
- Each item must have: `file_path`, `bug_type` (from the fixed enum), `line_number` (int or null), `description` (starts with lowercase verb), `raw_output`
- Strip accidental markdown fences before `json.loads()`
- On parse failure: fallback to a single generic LOGIC failure entry, never crash the loop

**Fix node prompt rules:**
- System prompt instructs: output ONLY valid JSON with keys `fixed_content` (full corrected file as string) and `explanation` (one line)
- Send the entire current file content alongside the failure description — the LLM needs full context
- Group all failures in the same file into one LLM call (don't call once per failure)
- On parse failure or `fixed_content: null`: mark that fix as `status: "failed"`, continue with other files

**Never send secrets to the LLM.** Before any file content goes into a prompt, strip values that match patterns for API keys, tokens, and `.env` entries.

---

## Frontend conventions

**`lib/api.ts` is the only file that knows `VITE_API_URL`.**
All components import typed functions from here, never raw `fetch`.

**`lib/ws.ts` is the only file that manages WebSocket connections.**
`useRun.ts` wraps both the REST polling fallback and the WS subscription into a single hook.

**Component responsibilities:**
- `InputSection` — controlled form, calls `runStore.startRun()`, shows validation errors
- `RunSummaryCard` — displays run metadata, live status badge, duration
- `ScoreBreakdown` — Recharts BarChart with 4 bars: Base, +Speed, -Penalty, Total
- `FixesTable` — one row per FixRecord, color-coded bug type badge, ✓/✗ status
- `CICDTimeline` — vertical list of CIResult entries with pass/fail dot + timestamp
- `StatusBadge` — reusable: `"passed"→green`, `"failed"→red`, `"running"→yellow`, `"pending"→gray`
- `RunHistory` — fetches `/api/runs`, click any row to call `runStore.loadRun(id)`

**Zustand store (`runStore.ts`) owns:**
- `activeRunId`, `activeRun`, `runHistory`, `isLoading`
- `startRun()` — POST to API, connect WS, kick off polling
- `loadRun()` — GET from API, set activeRun
- `loadHistory()` — GET /api/runs

---

## Separation of concerns — critical rules

| Layer | Allowed to touch | NOT allowed to touch |
|---|---|---|
| `agent/` | `AgentState`, tools, Anthropic SDK | FastAPI, SQLAlchemy, WebSocket |
| `api/` | FastAPI, WebSocket manager, route schemas | LangGraph, SQLAlchemy directly |
| `services/` | Both agent graph and DB session | HTTP request/response objects |
| `models/` | SQLAlchemy only | Everything else |
| `lib/api.ts` | `fetch`, env var for base URL | Store, components |
| `store/` | `lib/api.ts`, `lib/ws.ts` | Direct fetch, DB |
| `components/` | Store, hooks | `lib/api.ts` directly, store internals |

---

## Recommended build order

Build backend-first, then frontend. Within backend, build bottom-up:

```
1. config.py + database.py
2. models/run.py
3. agent/state.py                ← define AgentState completely before touching nodes
4. agent/tools/github.py
5. agent/tools/sandbox.py
6. agent/tools/stack_detector.py
7. agent/nodes/analyze.py
8. agent/nodes/run_tests.py
9. agent/nodes/diagnose.py
10. agent/nodes/fix.py
11. agent/nodes/commit.py
12. agent/nodes/monitor_ci.py
13. agent/graph.py
14. services/scorer.py
15. services/result_builder.py
16. services/runner.py
17. api/ws.py
18. api/routes/runs.py
19. api/routes/health.py
20. main.py
21. frontend/src/types/index.ts
22. frontend/src/lib/api.ts + ws.ts
23. frontend/src/store/runStore.ts
24. frontend/src/hooks/useRun.ts
25. frontend/src/components/ (one at a time, starting with StatusBadge)
26. frontend/src/App.tsx
```

---

## Known simplifications (personal use, not production)

- No Docker sandbox — tests run in subprocess with the same Python/Node environment as the server. Add Docker isolation later.
- No job queue — agent runs as a `asyncio.create_task()` background coroutine. Add Redis/Celery when concurrent runs are needed.
- No auth — single user, local only.
- No multi-tenancy — single `workspace_dir`, single DB, no org_id scoping.
- SQLite — swap to Postgres by changing `DATABASE_URL`. SQLAlchemy async is already abstracted.
- GitHub Actions only — no GitLab CI, no CircleCI support yet.
- No flaky test detection — every failure is treated as a real regression.

---

## The "no CI" edge case

Most personal repos won't have GitHub Actions configured. When `monitor_ci` finds zero workflow runs on the branch, treat the most recent `run_tests` result as ground truth:
- `all_tests_passing == True` → treat as `"passed"`
- `all_tests_passing == False` → treat as `"failed"`

Set `ci_result.status = "no_ci"` in the record so the dashboard can display it accurately.

---

## results.json — written at end of every run

Written to `{workspace_path}/results.json` by `services/result_builder.py`:

```json
{
  "run_id": "...",
  "repo_url": "...",
  "team_name": "...",
  "leader_name": "...",
  "branch_name": "...",
  "detected_stack": "python",
  "status": "passed",
  "total_failures": 3,
  "total_fixes_applied": 3,
  "total_commits": 2,
  "duration_seconds": 187.4,
  "score": {
    "base_score": 100,
    "speed_bonus": 10,
    "efficiency_penalty": 0,
    "final_score": 110
  },
  "fixes": [
    {
      "file": "src/utils.py",
      "bug_type": "LINTING",
      "line_number": 15,
      "commit_message": "Fix LINTING in src/utils.py line 15",
      "description": "LINTING error in src/utils.py line 15 → Fix: remove the unused import statement",
      "status": "fixed"
    }
  ],
  "ci_timeline": [
    {
      "iteration": 1,
      "status": "passed",
      "failures_found": 3,
      "fixes_applied": 3,
      "timestamp": "2026-06-23T10:15:42Z",
      "log_summary": "Iteration 1: fix 3 issue(s) (LINTING, SYNTAX, IMPORT)"
    }
  ],
  "error": null,
  "started_at": "2026-06-23T10:12:34Z",
  "finished_at": "2026-06-23T10:15:41Z"
}
```
