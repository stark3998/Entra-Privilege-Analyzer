// frontend/src/pages/BestPracticesPage.tsx
import { useState, useCallback } from "react";
import clsx from "clsx";
import {
  useViolations,
  useBestPracticeSummary,
  useEvaluateBestPractices,
} from "@/api/hooks";
import { useAuth } from "@/auth/useAuth";
import { ViolationList } from "@/components/best-practices/ViolationList";
import { ComplianceGauge } from "@/components/best-practices/ComplianceGauge";
import type { ViolationType, ViolationPriority } from "@/api/types";

const VIOLATION_TYPE_OPTIONS: { label: string; value: ViolationType | "" }[] = [
  { label: "All Types", value: "" },
  { label: "Stale Identity", value: "stale_identity" },
  { label: "Permanent Admin", value: "permanent_admin" },
  { label: "No PIM", value: "no_pim" },
  { label: "Credential Expiry", value: "sp_credential_expiry" },
  { label: "Separation of Duties", value: "separation_of_duties" },
  { label: "Overprivileged", value: "overprivileged" },
  { label: "MFA Gap", value: "mfa_gap" },
  { label: "Role-Assignable Group", value: "role_assignable_group" },
];

const PRIORITY_OPTIONS: { label: string; value: ViolationPriority | "" }[] = [
  { label: "All Priorities", value: "" },
  { label: "Critical", value: "critical" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
  { label: "Info", value: "info" },
];

const PAGE_SIZE = 20;

const PRIORITY_CARD_COLORS: Record<string, { bg: string; text: string }> = {
  critical: {
    bg: "bg-red-100 dark:bg-red-900/30",
    text: "text-red-700 dark:text-red-300",
  },
  high: {
    bg: "bg-orange-100 dark:bg-orange-900/30",
    text: "text-orange-700 dark:text-orange-300",
  },
  medium: {
    bg: "bg-amber-100 dark:bg-amber-900/30",
    text: "text-amber-700 dark:text-amber-300",
  },
  low: {
    bg: "bg-slate-100 dark:bg-slate-700",
    text: "text-slate-700 dark:text-slate-300",
  },
};

export function BestPracticesPage() {
  const [typeFilter, setTypeFilter] = useState<ViolationType | "">("");
  const [priorityFilter, setPriorityFilter] = useState<ViolationPriority | "">("");
  const [page, setPage] = useState(1);

  const { roles } = useAuth();
  const isIAMAdmin = roles.includes("IAMAdmin");

  const handleTypeChange = useCallback((value: string) => {
    setTypeFilter(value as ViolationType | "");
    setPage(1);
  }, []);

  const handlePriorityChange = useCallback((value: string) => {
    setPriorityFilter(value as ViolationPriority | "");
    setPage(1);
  }, []);

  const { data: violationsData, isLoading: violationsLoading } = useViolations({
    type: typeFilter || undefined,
    priority: priorityFilter || undefined,
    page,
    size: PAGE_SIZE,
  });

  const { data: summary } = useBestPracticeSummary();
  const evaluateMutation = useEvaluateBestPractices();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Best Practice Compliance
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Evaluate identity configurations against Entra ID security best
            practices
          </p>
        </div>

        {/* Evaluate button -- IAMAdmin only */}
        {isIAMAdmin && (
          <button
            onClick={() => evaluateMutation.mutate()}
            disabled={evaluateMutation.isPending}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors",
              evaluateMutation.isPending
                ? "cursor-not-allowed bg-brand-400 dark:bg-brand-600"
                : "bg-brand-600 hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600",
            )}
          >
            {evaluateMutation.isPending ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Evaluating...
              </>
            ) : (
              <>
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Evaluate
              </>
            )}
          </button>
        )}
      </div>

      {/* Success/Error banner for evaluate */}
      {evaluateMutation.isSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          Best practice evaluation completed successfully. Results are now
          loading.
        </div>
      )}
      {evaluateMutation.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to evaluate best practices:{" "}
          {evaluateMutation.error instanceof Error
            ? evaluateMutation.error.message
            : "Unknown error"}
        </div>
      )}

      {/* Compliance score gauge + summary cards */}
      {summary && (
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
          {/* Gauge */}
          <div className="flex-shrink-0">
            <ComplianceGauge score={summary.compliance_score} size={140} />
          </div>

          {/* Priority summary cards */}
          <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
            {(["critical", "high", "medium", "low"] as const).map((priority) => (
              <div
                key={priority}
                className={clsx(
                  "rounded-lg px-4 py-3",
                  PRIORITY_CARD_COLORS[priority]?.bg ?? "bg-slate-100 dark:bg-slate-700",
                )}
              >
                <p
                  className={clsx(
                    "text-xs font-medium capitalize",
                    PRIORITY_CARD_COLORS[priority]?.text ?? "text-slate-700 dark:text-slate-300",
                  )}
                >
                  {priority}
                </p>
                <p
                  className={clsx(
                    "mt-1 text-2xl font-bold tabular-nums",
                    PRIORITY_CARD_COLORS[priority]?.text ?? "text-slate-700 dark:text-slate-300",
                  )}
                >
                  {summary.by_priority[priority] ?? 0}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* Violation type filter */}
        <select
          value={typeFilter}
          onChange={(e) => handleTypeChange(e.target.value)}
          aria-label="Filter by violation type"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
        >
          {VIOLATION_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Priority filter */}
        <select
          value={priorityFilter}
          onChange={(e) => handlePriorityChange(e.target.value)}
          aria-label="Filter by priority"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
        >
          {PRIORITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Violation cards */}
      <ViolationList
        data={violationsData?.items ?? []}
        total={violationsData?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={violationsLoading}
      />
    </div>
  );
}
