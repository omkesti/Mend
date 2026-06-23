import clsx from "clsx";
import type { BugType, FixRecord } from "../types";

const BUG_COLORS: Record<BugType, string> = {
  LINTING: "bg-amber-100 text-amber-800",
  SYNTAX: "bg-rose-100 text-rose-800",
  LOGIC: "bg-violet-100 text-violet-800",
  TYPE_ERROR: "bg-sky-100 text-sky-800",
  IMPORT: "bg-emerald-100 text-emerald-800",
  INDENTATION: "bg-fuchsia-100 text-fuchsia-800",
};

export default function FixesTable({ fixes }: { fixes: FixRecord[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Fixes</h3>
      </div>

      {fixes.length === 0 ? (
        <p className="px-6 py-8 text-center text-sm text-slate-400">No fixes recorded.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr className="text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                <th className="px-6 py-3">File</th>
                <th className="px-6 py-3">Bug Type</th>
                <th className="px-6 py-3">Line</th>
                <th className="px-6 py-3">Description</th>
                <th className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {fixes.map((fix) => (
                <tr key={fix.id} className="hover:bg-slate-50">
                  <td className="whitespace-nowrap px-6 py-3 font-mono text-xs text-slate-700">
                    {fix.file_path}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={clsx(
                        "inline-flex rounded px-2 py-0.5 text-xs font-semibold",
                        BUG_COLORS[fix.bug_type]
                      )}
                    >
                      {fix.bug_type}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-slate-500">{fix.line_number ?? "—"}</td>
                  <td className="max-w-md px-6 py-3 text-slate-600">{fix.description}</td>
                  <td className="px-6 py-3">
                    {fix.status === "fixed" ? (
                      <span className="font-medium text-green-600">✓ Fixed</span>
                    ) : (
                      <span className="font-medium text-red-600">✗ Failed</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
