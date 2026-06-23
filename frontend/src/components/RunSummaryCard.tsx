import type { AgentRun } from "../types";
import { shortRepo } from "../lib/format";
import StatusBadge from "./StatusBadge";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-slate-900">{value}</div>
    </div>
  );
}

export default function RunSummaryCard({ run }: { run: AgentRun }) {
  const running = run.status === "running";
  const duration = run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : "—";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <a
              href={run.repo_url}
              target="_blank"
              rel="noreferrer"
              className="truncate text-lg font-semibold text-indigo-600 hover:underline"
            >
              {shortRepo(run.repo_url)}
            </a>
            {running && (
              <span className="relative flex h-2.5 w-2.5" title="Run in progress">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-yellow-400 opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-yellow-500" />
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {run.team_name} · {run.leader_name}
          </p>
          <p className="mt-1 font-mono text-xs text-slate-400">{run.branch_name}</p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Failures" value={run.total_failures} />
        <Stat label="Fixes" value={run.total_fixes} />
        <Stat label="Commits" value={run.total_commits} />
        <Stat label="Duration" value={duration} />
      </div>

      {run.error_message && (
        <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{run.error_message}</p>
      )}
    </div>
  );
}
