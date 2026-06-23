import clsx from "clsx";
import type { RunStatus } from "../types";

const STYLES: Record<RunStatus, string> = {
  passed: "bg-green-100 text-green-800 ring-green-600/20",
  failed: "bg-red-100 text-red-800 ring-red-600/20",
  running: "bg-yellow-100 text-yellow-800 ring-yellow-600/20",
  pending: "bg-gray-100 text-gray-700 ring-gray-500/20",
};

export default function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset",
        STYLES[status]
      )}
    >
      {status}
    </span>
  );
}
