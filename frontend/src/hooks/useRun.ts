// Polling fallback for a run: fetches every 3s until the run reaches a terminal
// status. The WebSocket is the primary live channel (wired in the store); this
// guarantees the UI converges even if the socket drops.

import { useEffect } from "react";
import { useRunStore } from "../store/runStore";
import type { AgentRun, RunStatus } from "../types";

const POLL_INTERVAL_MS = 3000;
const TERMINAL: ReadonlySet<RunStatus> = new Set<RunStatus>(["passed", "failed"]);

export function useRun(runId: string | null): AgentRun | null {
  const activeRun = useRunStore((s) => s.activeRun);
  const loadRun = useRunStore((s) => s.loadRun);

  useEffect(() => {
    if (!runId) return;

    // Fetch immediately so the UI doesn't wait a full interval.
    void loadRun(runId).catch(() => {});

    const intervalId = setInterval(() => {
      const current = useRunStore.getState().activeRun;
      if (current && current.id === runId && TERMINAL.has(current.status)) {
        clearInterval(intervalId);
        return;
      }
      void loadRun(runId).catch(() => {});
    }, POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [runId, loadRun]);

  return activeRun;
}
