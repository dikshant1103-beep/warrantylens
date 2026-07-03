import type { ClaimStatus } from "@/lib/types";

const STYLES: Record<ClaimStatus, string> = {
  draft: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  queued: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  processing: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  ready_for_review: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
  reviewed: "bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300",
  needs_more_evidence: "bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

export function StatusBadge({ status }: { status: ClaimStatus }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status] ?? "bg-slate-100"}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
