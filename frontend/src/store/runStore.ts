// Zustand store: owns the active run, history, and the live WS connection.
// Components read state from here; they never call lib/api or lib/ws directly.

import { create } from "zustand";
import * as api from "../lib/api";
import { AgentWS } from "../lib/ws";
import type { AgentRun, RunListItem, RunStatus } from "../types";

interface RunStore {
  activeRunId: string | null;
  activeRun: AgentRun | null;
  runHistory: RunListItem[];
  isLoading: boolean;
  _ws: AgentWS | null;

  startRun: (repoUrl: string, teamName: string, leaderName: string) => Promise<void>;
  loadRun: (runId: string) => Promise<void>;
  loadHistory: () => Promise<void>;
  _connectWs: (runId: string) => void;
  _disconnectWs: () => void;
}

export const useRunStore = create<RunStore>((set, get) => ({
  activeRunId: null,
  activeRun: null,
  runHistory: [],
  isLoading: false,
  _ws: null,

  startRun: async (repoUrl, teamName, leaderName) => {
    set({ isLoading: true });
    try {
      const res = await api.startRun(repoUrl, teamName, leaderName);
      // The run record isn't readable yet; the hook's poll + WS will populate it.
      set({ activeRunId: res.run_id, activeRun: null, isLoading: false });
      get()._connectWs(res.run_id);
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  loadRun: async (runId) => {
    set({ isLoading: true });
    try {
      const run = await api.getRun(runId);
      set({ activeRun: run, activeRunId: runId, isLoading: false });
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  loadHistory: async () => {
    const list = await api.listRuns();
    set({ runHistory: list });
  },

  _connectWs: (runId) => {
    get()._disconnectWs();
    const ws = new AgentWS(runId, {
      onStatus: (data) => {
        set((s) =>
          s.activeRun
            ? { activeRun: { ...s.activeRun, status: data.status as RunStatus } }
            : {}
        );
      },
      onComplete: () => {
        // The complete payload is the results dict, not the AgentRun shape —
        // refetch the canonical record, refresh history, then close the socket.
        void get()
          .loadRun(runId)
          .then(() => get().loadHistory())
          .catch(() => {});
        get()._disconnectWs();
      },
      onError: (data) => {
        set((s) =>
          s.activeRun
            ? { activeRun: { ...s.activeRun, status: "failed", error_message: data.message } }
            : {}
        );
        void get().loadRun(runId).catch(() => {});
        get()._disconnectWs();
      },
    });
    set({ _ws: ws });
  },

  _disconnectWs: () => {
    const ws = get()._ws;
    if (ws) {
      ws.disconnect();
      set({ _ws: null });
    }
  },
}));
