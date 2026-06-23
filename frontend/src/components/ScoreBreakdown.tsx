import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RunStatus, ScoreBreakdown as Score } from "../types";

const COLORS = {
  base: "#3b82f6", // blue
  speed: "#22c55e", // green
  penalty: "#ef4444", // red
  total: "#6366f1", // indigo
};

export default function ScoreBreakdown({ score, status }: { score: Score; status: RunStatus }) {
  const finalized = status === "passed" || status === "failed";

  const data = [
    { name: "Base", value: score.base_score, color: COLORS.base },
    { name: "+Speed", value: score.speed_bonus, color: COLORS.speed },
    { name: "-Penalty", value: score.efficiency_penalty, color: COLORS.penalty },
    { name: "Total", value: score.final_score, color: COLORS.total },
  ];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Score</h3>

      <div className="mt-2 flex items-end gap-2">
        <span className="text-5xl font-bold text-slate-900">{score.final_score}</span>
        <span className="mb-1 text-sm text-slate-400">/ final</span>
      </div>
      {!finalized && (
        <p className="mt-1 text-xs text-amber-600">Score finalizes when the run completes.</p>
      )}

      <dl className="mt-4 space-y-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">Base</dt>
          <dd className="font-medium text-slate-900">{score.base_score}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Speed bonus</dt>
          <dd className="font-medium text-green-600">+{score.speed_bonus}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Efficiency penalty</dt>
          <dd className="font-medium text-red-600">-{score.efficiency_penalty}</dd>
        </div>
      </dl>

      <div className="mt-4 h-40">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#64748b" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 12, fill: "#64748b" }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "rgba(0,0,0,0.04)" }} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {data.map((entry) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
