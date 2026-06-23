// Typed fetch wrappers. This is the ONLY file that knows the API base URL.

import type { AgentRun, RunListItem } from "../types";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface StartRunResponse {
  run_id: string;
  branch_name: string;
  status: string;
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function startRun(
  repoUrl: string,
  teamName: string,
  leaderName: string
): Promise<StartRunResponse> {
  const res = await fetch(`${API_BASE}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      repo_url: repoUrl,
      team_name: teamName,
      leader_name: leaderName,
    }),
  });
  return parse<StartRunResponse>(res);
}

export async function getRun(runId: string): Promise<AgentRun> {
  const res = await fetch(`${API_BASE}/api/runs/${runId}`);
  return parse<AgentRun>(res);
}

export async function listRuns(): Promise<RunListItem[]> {
  const res = await fetch(`${API_BASE}/api/runs`);
  return parse<RunListItem[]>(res);
}
