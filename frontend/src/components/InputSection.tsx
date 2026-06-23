import { useState, type FormEvent } from "react";
import { useRunStore } from "../store/runStore";

export default function InputSection() {
  const startRun = useRunStore((s) => s.startRun);
  const isLoading = useRunStore((s) => s.isLoading);
  const activeStatus = useRunStore((s) => s.activeRun?.status);
  const running = isLoading || activeStatus === "running";

  const [repoUrl, setRepoUrl] = useState("");
  const [teamName, setTeamName] = useState("");
  const [leaderName, setLeaderName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!repoUrl.trim() || !teamName.trim() || !leaderName.trim()) {
      setError("All fields are required.");
      return;
    }
    if (!repoUrl.includes("github.com")) {
      setError("Repository URL must be a github.com URL.");
      return;
    }
    setError(null);
    try {
      await startRun(repoUrl.trim(), teamName.trim(), leaderName.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run.");
    }
  };

  const inputClass =
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-100 disabled:text-slate-400";

  return (
    <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">Heal a repository</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Repository URL</span>
          <input
            className={inputClass}
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            disabled={running}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Team name</span>
          <input
            className={inputClass}
            placeholder="RIFT Organisers"
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
            disabled={running}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Leader name</span>
          <input
            className={inputClass}
            placeholder="Saiyam Kumar"
            value={leaderName}
            onChange={(e) => setLeaderName(e.target.value)}
            disabled={running}
          />
        </label>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={running}
        className="mt-4 inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {running ? (
          <>
            <span className="mr-2 h-2 w-2 animate-pulse rounded-full bg-white" />
            AGENT RUNNING...
          </>
        ) : (
          "Heal Repository"
        )}
      </button>
    </form>
  );
}
