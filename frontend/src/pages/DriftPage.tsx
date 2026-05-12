// frontend/src/pages/DriftPage.tsx
import { useState, useEffect, useCallback, useRef } from "react";
import clsx from "clsx";
import { useDriftAlerts, useDetectDrift } from "@/api/hooks";
import { useAuth } from "@/auth/useAuth";
import { DriftAlertTable } from "@/components/drift/DriftAlertTable";
import type { DriftSeverity, DriftStatus } from "@/api/types";

const SEVERITY_OPTIONS: { label: string; value: DriftSeverity | "" }[] = [
  { label: "All Severities", value: "" },
  { label: "Critical", value: "critical" },
  { label: "High", value: "high" },
  { label: "Medium", value: "medium" },
  { label: "Low", value: "low" },
];

const STATUS_OPTIONS: { label: string; value: DriftStatus | "" }[] = [
  { label: "All Statuses", value: "" },
  { label: "Open", value: "open" },
  { label: "Acknowledged", value: "acknowledged" },
  { label: "Escalated", value: "escalated" },
  { label: "Resolved", value: "resolved" },
];

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

const SEVERITY_BADGE_COLORS: Record<DriftSeverity, { bg: string; text: string }> = {
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

export function DriftPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<DriftSeverity | "">("");
  const [statusFilter, setStatusFilter] = useState<DriftStatus | "">("");
  const [page, setPage] = useState(1);

  const { roles } = useAuth();
  const isIAMAdmin = roles.includes("IAMAdmin");

  // Debounce search input
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(1);
    }, DEBOUNCE_MS);
  }, []);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleSeverityChange = useCallback((value: string) => {
    setSeverityFilter(value as DriftSeverity | "");
    setPage(1);
  }, []);

  const handleStatusChange = useCallback((value: string) => {
    setStatusFilter(value as DriftStatus | "");
    setPage(1);
  }, []);

  const { data, isLoading } = useDriftAlerts({
    severity: severityFilter || undefined,
    status: statusFilter || undefined,
    search: debouncedSearch || undefined,
    page,
    size: PAGE_SIZE,
  });

  const detectMutation = useDetectDrift();

  // Compute severity counts from the current data for the badges
  // These show counts from the current page results; a production implementation
  // would use a separate summary endpoint for global counts.
  const alerts = data?.items ?? [];
  const severityCounts: Record<DriftSeverity, number> = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  };
  for (const alert of alerts) {
    severityCounts[alert.severity]++;
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Permission Drift Monitor
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Detect anomalous permission usage and first-seen actions across
            identities
          </p>
        </div>

        {/* Run Detection button -- IAMAdmin only */}
        {isIAMAdmin && (
          <button
            onClick={() => detectMutation.mutate()}
            disabled={detectMutation.isPending}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors",
              detectMutation.isPending
                ? "cursor-not-allowed bg-brand-400 dark:bg-brand-600"
                : "bg-brand-600 hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600",
            )}
          >
            {detectMutation.isPending ? (
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
                Detecting...
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
                    d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                  />
                </svg>
                Run Detection
              </>
            )}
          </button>
        )}
      </div>

      {/* Success/Error banner for detection */}
      {detectMutation.isSuccess && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          Drift detection completed successfully. Results are now loading.
        </div>
      )}
      {detectMutation.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to run drift detection:{" "}
          {detectMutation.error instanceof Error
            ? detectMutation.error.message
            : "Unknown error"}
        </div>
      )}

      {/* Severity count badges */}
      <div className="flex flex-wrap gap-3">
        {(
          ["critical", "high", "medium", "low"] as const
        ).map((sev) => (
          <div
            key={sev}
            className={clsx(
              "flex items-center gap-2 rounded-lg px-3 py-2",
              SEVERITY_BADGE_COLORS[sev].bg,
            )}
          >
            <span
              className={clsx(
                "text-sm font-medium capitalize",
                SEVERITY_BADGE_COLORS[sev].text,
              )}
            >
              {sev}
            </span>
            <span
              className={clsx(
                "text-lg font-bold tabular-nums",
                SEVERITY_BADGE_COLORS[sev].text,
              )}
            >
              {severityCounts[sev]}
            </span>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1">
          <svg
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search by identity name..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-10 pr-4 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-white dark:placeholder:text-slate-500 dark:focus:border-brand-400 dark:focus:ring-brand-400"
          />
        </div>

        {/* Severity filter */}
        <select
          value={severityFilter}
          onChange={(e) => handleSeverityChange(e.target.value)}
          aria-label="Filter by severity"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
        >
          {SEVERITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={(e) => handleStatusChange(e.target.value)}
          aria-label="Filter by status"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300 dark:focus:border-brand-400 dark:focus:ring-brand-400"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Drift alert table */}
      <DriftAlertTable
        data={alerts}
        total={data?.total ?? 0}
        page={page}
        pageSize={PAGE_SIZE}
        onPageChange={setPage}
        isLoading={isLoading}
      />
    </div>
  );
}
