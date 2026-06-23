// Shared TypeScript types — mirror the backend's serialized shapes.

export type BugType =
  | "LINTING"
  | "SYNTAX"
  | "LOGIC"
  | "TYPE_ERROR"
  | "IMPORT"
  | "INDENTATION";

export type RunStatus = "pending" | "running" | "passed" | "failed";

export type FixStatus = "fixed" | "failed";

export type CIStatus = "passed" | "failed" | "pending" | "no_ci";

export interface FixRecord {
  id: number;
  file_path: string;
  bug_type: BugType;
  line_number: number | null;
  commit_message: string;
  status: FixStatus;
  description: string;
  created_at: string | null;
}

export interface CIIteration {
  id: number;
  iteration_number: number;
  status: CIStatus;
  failures_found: number;
  fixes_applied: number;
  timestamp: string | null;
  log_summary: string | null;
}

export interface ScoreBreakdown {
  base_score: number;
  speed_bonus: number;
  efficiency_penalty: number;
  final_score: number;
}

// Summary shape returned by GET /api/runs.
export interface RunListItem {
  id: string;
  repo_url: string;
  team_name: string;
  leader_name: string;
  branch_name: string;
  status: RunStatus;
  total_failures: number;
  total_fixes: number;
  total_commits: number;
  final_score: number;
  duration_seconds: number | null;
  started_at: string | null;
  finished_at: string | null;
}

// Full detail returned by GET /api/runs/{id}.
export interface AgentRun extends RunListItem {
  base_score: number;
  speed_bonus: number;
  efficiency_penalty: number;
  error_message: string | null;
  fixes: FixRecord[];
  ci_iterations: CIIteration[];
}
