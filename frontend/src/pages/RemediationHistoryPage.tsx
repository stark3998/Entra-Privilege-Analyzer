// frontend/src/pages/RemediationHistoryPage.tsx
import { useState } from "react";
import clsx from "clsx";
import { useRemediationActions } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import type { RemediationAction } from "@/api/types";

const PAGE_SIZE = 50;

const STATUS_STYLE: Record<string, { bg: string; text: string }> = {
  pending: { bg: "bg-amber-50 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-300" },
  approved: { bg: "bg-blue-50 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-300" },
  in_progress: { bg: "bg-brand-50 dark:bg-brand-900/30", text: "text-brand-700 dark:text-brand-300" },
  completed: { bg: "bg-emerald-50 dark:bg-emerald-900/30", text: "text-emerald-700 dark:text-emerald-300" },
  failed: { bg: "bg-red-50 dark:bg-red-900/30", text: "text-red-700 dark:text-red-300" },
  cancelled: { bg: "bg-slate-100 dark:bg-slate-700", text: "text-slate-600 dark:text-slate-300" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusLabel(status: string): string {
  return status
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function RemediationHistoryPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useRemediationActions(page, PAGE_SIZE);

  const items: RemediationAction[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Remediation History</h1>
        <p className="page-subtitle">
          Track remediation actions, their approval status, and execution results
        </p>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading remediation actions..." />
      ) : items.length === 0 ? (
        <EmptyState
          title="No remediation actions"
          description="Remediation actions will appear here once triggered from recommendations or policies."
          icon={
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.1-5.1m0 0L11.42 4.97m-5.1 5.1H21M3 3v18" />
            </svg>
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Action Type</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Target</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Requested By</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((action) => {
                  const style = STATUS_STYLE[action.status] ?? STATUS_STYLE.pending;
                  return (
                    <tr key={action.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                          {statusLabel(action.action_type)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm font-medium text-slate-900 dark:text-white">
                          {action.target_identity_id}
                        </div>
                        {action.target_resource_id && (
                          <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 line-clamp-1">
                            {action.target_resource_id}
                          </div>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-700 dark:text-slate-300">
                        {action.requested_by}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center">
                        <span
                          className={clsx(
                            "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
                            style.bg,
                            style.text,
                          )}
                        >
                          {statusLabel(action.status)}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                        {formatDate(action.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
