// frontend/src/components/drift/DriftAlertTable.tsx
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import type { DriftAlert, DriftType, DriftStatus } from "@/api/types";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface DriftAlertTableProps {
  data: DriftAlert[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading: boolean;
}

const DRIFT_TYPE_COLORS: Record<DriftType, string> = {
  first_seen: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  frequency_anomaly: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
};

const DRIFT_TYPE_LABELS: Record<DriftType, string> = {
  first_seen: "First Seen",
  frequency_anomaly: "Frequency Anomaly",
};

const STATUS_COLORS: Record<DriftStatus, string> = {
  open: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  acknowledged: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  escalated: "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  resolved: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
};

const SKELETON_ROWS = 5;

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-20 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
        </td>
      ))}
    </tr>
  );
}

/**
 * Table of drift alerts with severity badges, status indicators,
 * clickable rows, loading skeletons, empty state, and pagination.
 */
export function DriftAlertTable({
  data,
  total,
  page,
  pageSize,
  onPageChange,
  isLoading,
}: DriftAlertTableProps) {
  const navigate = useNavigate();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  if (isLoading) {
    return (
      <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800/50">
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Severity</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Identity</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Action</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Drift Type</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Detected</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Z-Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <EmptyState
        title="No drift alerts found"
        description="No permission drift has been detected yet. Run detection to scan for anomalous activity."
        icon={
          <svg
            className="h-10 w-10"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
            />
          </svg>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Severity</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Identity</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Action</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Drift Type</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Status</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Detected</th>
                <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Z-Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.map((alert) => (
                <tr
                  key={alert.id}
                  onClick={() => navigate(`/drift/${alert.id}`)}
                  className="cursor-pointer transition-colors hover:bg-brand-50/50 dark:hover:bg-brand-900/10"
                >
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <SeverityBadge severity={alert.severity} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-sm font-medium text-slate-900 dark:text-white">
                    {alert.identity_display_name}
                  </td>
                  <td className="max-w-xs truncate px-4 py-2.5 text-sm text-slate-600 dark:text-slate-400" title={alert.action}>
                    {alert.action}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span
                      className={clsx(
                        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                        DRIFT_TYPE_COLORS[alert.drift_type],
                      )}
                    >
                      {DRIFT_TYPE_LABELS[alert.drift_type]}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <span
                      className={clsx(
                        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                        STATUS_COLORS[alert.status],
                      )}
                    >
                      {alert.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-sm text-slate-500 dark:text-slate-400">
                    {formatRelativeTime(alert.detected_at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-sm tabular-nums text-slate-700 dark:text-slate-300">
                    {alert.z_score != null ? alert.z_score.toFixed(1) : (
                      <span className="text-slate-400 dark:text-slate-500">--</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Showing {startItem}&ndash;{endItem} of {total}
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                page <= 1
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )}
            >
              Prev
            </button>
            <span className="px-2 text-xs font-medium text-slate-500 dark:text-slate-400">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
                page >= totalPages
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
