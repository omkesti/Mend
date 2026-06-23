import clsx from "clsx";
import type { CIIteration, CIStatus, RunStatus } from "../types";

const DOT: Record<CIStatus, string> = {
  passed: "bg-green-500",
  failed: "bg-red-500",
  pending: "bg-amber-400",
  no_ci: "bg-slate-400",
};

function fmtTime(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleTimeString();
}

export default function CICDTimeline({
  iterations,
  maxRetries,
  status,
}: {
  iterations: CIIteration[];
  maxRetries: number;
  status: RunStatus;
}) {
  const byNum = new Map(iterations.map((it) => [it.iteration_number, it]));
  const rowCount = Math.max(maxRetries, iterations.length);
  // The iteration currently in flight gets the pulse while the run is active.
  const pulsingNum = status === "running" ? Math.min(iterations.length + 1, rowCount) : -1;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">
        CI/CD Timeline
      </h3>
      <ol className="space-y-2">
        {Array.from({ length: rowCount }, (_, i) => {
          const num = i + 1;
          const it = byNum.get(num) ?? null;
          const pulsing = num === pulsingNum;

          return (
            <li
              key={num}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2",
                it ? "bg-slate-50" : "bg-transparent"
              )}
            >
              <span className="relative flex h-3 w-3 shrink-0">
                {pulsing && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                )}
                <span
                  className={clsx(
                    "relative inline-flex h-3 w-3 rounded-full",
                    it ? DOT[it.status] : "border border-slate-300 bg-slate-200"
                  )}
                />
              </span>

              <span className="w-16 shrink-0 text-xs font-semibold text-slate-700">
                Iter {num}
              </span>

              {it ? (
                <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
                  <span className="truncate text-sm text-slate-700">{it.log_summary}</span>
                  <span className="flex shrink-0 items-center gap-3 text-xs text-slate-400">
                    <span>{it.failures_found} found · {it.fixes_applied} fixed</span>
                    <span>{fmtTime(it.timestamp)}</span>
                  </span>
                </div>
              ) : (
                <span className="flex-1 text-sm text-slate-300">
                  {pulsing ? "in progress…" : "pending"}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
