import { useState } from "react";
import { useRunStore } from "./store/runStore";
import { useRun } from "./hooks/useRun";
import InputSection from "./components/InputSection";
import RunSummaryCard from "./components/RunSummaryCard";
import ScoreBreakdown from "./components/ScoreBreakdown";
import CICDTimeline from "./components/CICDTimeline";
import FixesTable from "./components/FixesTable";
import RunHistory from "./components/RunHistory";

// The backend's default MAX_RETRIES (not exposed via the API); used to render
// the timeline's pending placeholder rows.
const MAX_RETRIES = 5;

export default function App() {
  const [showHistory, setShowHistory] = useState(false);

  const activeRunId = useRunStore((s) => s.activeRunId);
  const isLoading = useRunStore((s) => s.isLoading);

  // Top-level polling fallback for the active run.
  const activeRun = useRun(activeRunId);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-xl font-bold">Mend</h1>
            <p className="text-xs text-slate-500">CI/CD Healing Agent</p>
          </div>
          <button
            type="button"
            onClick={() => setShowHistory((v) => !v)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {showHistory ? "← Back to run" : "Run history"}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        {showHistory ? (
          <RunHistory onSelect={() => setShowHistory(false)} />
        ) : (
          <>
            <InputSection />

            {isLoading && !activeRun && (
              <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-400 shadow-sm">
                Starting agent…
              </div>
            )}

            {activeRun && (
              <>
                {activeRun.error_message && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {activeRun.error_message}
                  </div>
                )}

                <RunSummaryCard run={activeRun} />

                <div className="grid gap-6 lg:grid-cols-2">
                  <ScoreBreakdown
                    score={{
                      base_score: activeRun.base_score,
                      speed_bonus: activeRun.speed_bonus,
                      efficiency_penalty: activeRun.efficiency_penalty,
                      final_score: activeRun.final_score,
                    }}
                    status={activeRun.status}
                  />
                  <CICDTimeline
                    iterations={activeRun.ci_iterations}
                    maxRetries={MAX_RETRIES}
                    status={activeRun.status}
                  />
                </div>

                <FixesTable fixes={activeRun.fixes} />
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
