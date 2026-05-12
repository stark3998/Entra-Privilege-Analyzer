// frontend/src/components/dashboard/DriftSummaryCard.tsx
import { Link } from "react-router-dom";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  low: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
};

interface DriftSummaryCardProps {
  /** Total number of open drift alerts. */
  total: number;
  /** Counts per severity level. */
  bySeverity: Record<string, number>;
}

/**
 * Card showing total open drift alerts with severity breakdown chips.
 *
 * Usage:
 * ```tsx
 * <DriftSummaryCard total={15} bySeverity={{ critical: 2, high: 5, medium: 6, low: 2 }} />
 * ```
 */
export function DriftSummaryCard({ total, bySeverity }: DriftSummaryCardProps) {
  const severities = ["critical", "high", "medium", "low"] as const;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
        Open Drift Alerts
      </p>
      <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
        {total.toLocaleString()}
      </p>

      {/* Severity chips */}
      <div className="mt-4 flex flex-wrap gap-2">
        {severities.map((sev) => {
          const count = bySeverity[sev] ?? 0;
          return (
            <span
              key={sev}
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${SEVERITY_COLORS[sev] ?? ""}`}
            >
              {sev}: {count}
            </span>
          );
        })}
      </div>

      {/* View all link */}
      <Link
        to="/drift"
        className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
      >
        View All
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </Link>
    </div>
  );
}
