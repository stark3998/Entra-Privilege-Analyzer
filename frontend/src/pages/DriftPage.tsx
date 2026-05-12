import { useState, useEffect, useCallback, useRef } from "react";
import clsx from "clsx";
import { useDriftAlerts, useDetectDrift } from "@/api/hooks";
import { useAuth } from "@/auth/useAuth";
import { DriftAlertTable } from "@/components/drift/DriftAlertTable";
import { Tooltip } from "@/components/common/Tooltip";
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

const SEVERITY_BADGE: Record<DriftSeverity, { bg: string; text: string; dot: string }> = {
  critical: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-700 dark:text-red-300", dot: "bg-red-500" },
  high: { bg: "bg-orange-50 dark:bg-orange-900/20", text: "text-orange-700 dark:text-orange-300", dot: "bg-orange-500" },
  medium: { bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-700 dark:text-amber-300", dot: "bg-amber-500" },
  low: { bg: "bg-slate-50 dark:bg-slate-800", text: "text-slate-700 dark:text-slate-300", dot: "bg-slate-400" },
};

export function DriftPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<DriftSeverity | "">("");
  const [statusFilter, setStatusFilter] = useState<DriftStatus | "">("");
  const [page, setPage] = useState(1);

  const { roles } = useAuth();
  const isIAMAdmin = roles.includes("IAMAdmin");

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => { setDebouncedSearch(value); setPage(1); }, DEBOUNCE_MS);
  }, []);
  useEffect(() => { return () => { if (timerRef.current) clearTimeout(timerRef.current); }; }, []);

  const { data, isLoading } = useDriftAlerts({
    severity: severityFilter || undefined,
    status: statusFilter || undefined,
    search: debouncedSearch || undefined,
    page,
    size: PAGE_SIZE,
  });

  const detectMutation = useDetectDrift();

  const alerts = data?.items ?? [];
  const severityCounts: Record<DriftSeverity, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const alert of alerts) severityCounts[alert.severity]++;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Permission Drift Monitor</h1>
          <p className="page-subtitle">
            Detect anomalous permission usage and first-seen actions across identities
          </p>
        </div>

        {isIAMAdmin && (
          <Tooltip content="Scan all identities for permission drift anomalies">
            <button type="button" onClick={() => detectMutation.mutate()} disabled={detectMutation.isPending} className="btn-primary">
              {detectMutation.isPending ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Detecting...
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  Run Detection
                </>
              )}
            </button>
          </Tooltip>
        )}
      </div>

      {detectMutation.isSuccess && (
        <div className="card border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          Drift detection completed successfully.
        </div>
      )}
      {detectMutation.isError && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to run drift detection: {detectMutation.error instanceof Error ? detectMutation.error.message : "Unknown error"}
        </div>
      )}

      {/* Severity count badges */}
      <div className="flex flex-wrap gap-3">
        {(["critical", "high", "medium", "low"] as const).map((sev) => {
          const s = SEVERITY_BADGE[sev];
          return (
            <div key={sev} className={clsx("flex items-center gap-2.5 rounded-xl px-4 py-2.5", s.bg)}>
              <span className={clsx("h-2 w-2 rounded-full", s.dot)} />
              <span className={clsx("text-sm font-semibold capitalize", s.text)}>{sev}</span>
              <span className={clsx("text-lg font-bold tabular-nums", s.text)}>{severityCounts[sev]}</span>
            </div>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <svg className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input type="text" placeholder="Search by identity name..." value={search} onChange={(e) => handleSearchChange(e.target.value)} className="input-base w-full pl-10" />
        </div>
        <select value={severityFilter} onChange={(e) => { setSeverityFilter(e.target.value as DriftSeverity | ""); setPage(1); }} aria-label="Filter by severity" className="input-base">
          {SEVERITY_OPTIONS.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
        </select>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as DriftStatus | ""); setPage(1); }} aria-label="Filter by status" className="input-base">
          {STATUS_OPTIONS.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
        </select>
      </div>

      <DriftAlertTable data={alerts} total={data?.total ?? 0} page={page} pageSize={PAGE_SIZE} onPageChange={setPage} isLoading={isLoading} />
    </div>
  );
}
