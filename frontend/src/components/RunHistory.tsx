import { useEffect } from "react";
import { useRunStore } from "../store/runStore";
import StatusBadge from "./StatusBadge";

function shortRepo(url: string): string {
  return url
    .replace(/\.git$/, "")
    .replace(/\/$/, "")
    .split("/")
    .slice(-2)
    .join("/");
}

export default function RunHistory({ onSelect }: { onSelect?: (runId: string) => void }) {
  const runHistory = useRunStore((s) => s.runHistory);
  const loadHistory = useRunStore((s) => s.loadHistory);
  const loadRun = useRunStore((s) => s.loadRun);

  useEffect(() => {
    void loadHistory().catch(() => {});
  }, [loadHistory]);

  const select = (runId: string) => {
    void loadRun(runId).catch(() => {});
    onSelect?.(runId);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">History</h3>

      {runHistory.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-400">No runs yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {runHistory.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                onClick={() => select(run.id)}
                className="flex w-full items-center justify-between gap-3 px-1 py-3 text-left hover:bg-slate-50"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-800">
                    {shortRepo(run.repo_url)}
                  </div>
                  <div className="truncate text-xs text-slate-400">{run.team_name}</div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-sm font-semibold text-slate-700">{run.final_score}</span>
                  <StatusBadge status={run.status} />
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
