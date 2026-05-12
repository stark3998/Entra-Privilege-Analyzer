import { useState, useCallback } from "react";
import clsx from "clsx";
import { useViolations, useBestPracticeSummary, useEvaluateBestPractices } from "@/api/hooks";
import { useAuth } from "@/auth/useAuth";
import { ViolationList } from "@/components/best-practices/ViolationList";
import { ComplianceGauge } from "@/components/best-practices/ComplianceGauge";
import { Tooltip } from "@/components/common/Tooltip";
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

const PRIORITY_CARD: Record<string, { bg: string; text: string; dot: string }> = {
  critical: { bg: "bg-red-50 dark:bg-red-900/20", text: "text-red-700 dark:text-red-300", dot: "bg-red-500" },
  high: { bg: "bg-orange-50 dark:bg-orange-900/20", text: "text-orange-700 dark:text-orange-300", dot: "bg-orange-500" },
  medium: { bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-700 dark:text-amber-300", dot: "bg-amber-500" },
  low: { bg: "bg-slate-50 dark:bg-slate-800", text: "text-slate-700 dark:text-slate-300", dot: "bg-slate-400" },
};

export function BestPracticesPage() {
  const [typeFilter, setTypeFilter] = useState<ViolationType | "">("");
  const [priorityFilter, setPriorityFilter] = useState<ViolationPriority | "">("");
  const [page, setPage] = useState(1);

  const { roles } = useAuth();
  const isIAMAdmin = roles.includes("IAMAdmin");

  const handleTypeChange = useCallback((value: string) => { setTypeFilter(value as ViolationType | ""); setPage(1); }, []);
  const handlePriorityChange = useCallback((value: string) => { setPriorityFilter(value as ViolationPriority | ""); setPage(1); }, []);

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
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Best Practice Compliance</h1>
          <p className="page-subtitle">
            Evaluate identity configurations against Entra ID security best practices
          </p>
        </div>

        {isIAMAdmin && (
          <Tooltip content="Run best practice evaluation against all identities">
            <button type="button" onClick={() => evaluateMutation.mutate()} disabled={evaluateMutation.isPending} className="btn-primary">
              {evaluateMutation.isPending ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Evaluating...
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Evaluate
                </>
              )}
            </button>
          </Tooltip>
        )}
      </div>

      {evaluateMutation.isSuccess && (
        <div className="card border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400">
          Evaluation completed successfully.
        </div>
      )}
      {evaluateMutation.isError && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed: {evaluateMutation.error instanceof Error ? evaluateMutation.error.message : "Unknown error"}
        </div>
      )}

      {summary && (
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
          <div className="flex-shrink-0">
            <ComplianceGauge score={summary.compliance_score} size={140} />
          </div>
          <div className="grid flex-1 grid-cols-2 gap-3 sm:grid-cols-4">
            {(["critical", "high", "medium", "low"] as const).map((priority) => {
              const c = PRIORITY_CARD[priority];
              return (
                <div key={priority} className={clsx("rounded-xl px-4 py-3", c?.bg)}>
                  <div className="flex items-center gap-1.5">
                    <span className={clsx("h-1.5 w-1.5 rounded-full", c?.dot)} />
                    <p className={clsx("text-xs font-semibold capitalize", c?.text)}>{priority}</p>
                  </div>
                  <p className={clsx("mt-1 text-2xl font-bold tabular-nums", c?.text)}>
                    {summary.by_priority[priority] ?? 0}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select value={typeFilter} onChange={(e) => handleTypeChange(e.target.value)} aria-label="Filter by violation type" className="input-base">
          {VIOLATION_TYPE_OPTIONS.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
        </select>
        <select value={priorityFilter} onChange={(e) => handlePriorityChange(e.target.value)} aria-label="Filter by priority" className="input-base">
          {PRIORITY_OPTIONS.map((opt) => (<option key={opt.value} value={opt.value}>{opt.label}</option>))}
        </select>
      </div>

      <ViolationList data={violationsData?.items ?? []} total={violationsData?.total ?? 0} page={page} pageSize={PAGE_SIZE} onPageChange={setPage} isLoading={violationsLoading} />
    </div>
  );
}
