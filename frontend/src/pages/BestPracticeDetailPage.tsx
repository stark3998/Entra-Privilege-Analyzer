// frontend/src/pages/BestPracticeDetailPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useViolationDetail } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { RemediationSteps } from "@/components/best-practices/RemediationSteps";
import { ApiError } from "@/api/client";
import { formatRelativeTime } from "@/utils/formatRelativeTime";
import type { ViolationType, ViolationPriority } from "@/api/types";

/** Color map for priority badges. */
const PRIORITY_COLORS: Record<ViolationPriority, { bg: string; dot: string }> = {
  critical: { bg: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300", dot: "bg-red-500" },
  high: { bg: "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300", dot: "bg-orange-500" },
  medium: { bg: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300", dot: "bg-amber-500" },
  low: { bg: "bg-slate-50 text-slate-700 dark:bg-slate-800 dark:text-slate-300", dot: "bg-slate-400" },
  info: { bg: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300", dot: "bg-blue-500" },
};

/** Color map for violation type badges. */
const VIOLATION_TYPE_COLORS: Record<ViolationType, string> = {
  stale_identity: "bg-slate-50 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  permanent_admin: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  no_pim: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  sp_credential_expiry: "bg-orange-50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  separation_of_duties: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  overprivileged: "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
  mfa_gap: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  role_assignable_group: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
};

const VIOLATION_TYPE_LABELS: Record<ViolationType, string> = {
  stale_identity: "Stale Identity",
  permanent_admin: "Permanent Admin",
  no_pim: "No PIM",
  sp_credential_expiry: "Credential Expiry",
  separation_of_duties: "Separation of Duties",
  overprivileged: "Overprivileged",
  mfa_gap: "MFA Gap",
  role_assignable_group: "Role-Assignable Group",
};

/** Color map for identity type badges. Matches IdentityDetail. */
const IDENTITY_TYPE_COLORS: Record<string, string> = {
  User: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  ServicePrincipal: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  ManagedIdentity: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  Group: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

export function BestPracticeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useViolationDetail(id ?? "");

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => navigate("../best-practices")}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-medium text-slate-600 transition-colors hover:bg-brand-50 hover:text-brand-700 dark:text-slate-400 dark:hover:bg-brand-900/20 dark:hover:text-brand-300"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Best Practices
      </button>

      {/* Loading */}
      {isLoading && (
        <LoadingSpinner message="Loading violation details..." />
      )}

      {/* Error / 404 */}
      {isError && (
        <EmptyState
          title={
            error instanceof ApiError && error.status === 404
              ? "Violation not found"
              : "Failed to load violation"
          }
          description={
            error instanceof ApiError && error.status === 404
              ? "This violation does not exist or has been removed."
              : error instanceof Error
                ? error.message
                : "An unexpected error occurred."
          }
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
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          }
          action={
            <button type="button" onClick={() => navigate("../best-practices")} className="btn-primary">
              Return to Best Practices
            </button>
          }
        />
      )}

      {/* Detail view */}
      {data && (
        <div className="space-y-8">
          {/* Header */}
          <div className="flex flex-wrap items-start gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className={clsx("badge capitalize", PRIORITY_COLORS[data.priority].bg)}>
                  <span className={clsx("h-1.5 w-1.5 rounded-full", PRIORITY_COLORS[data.priority].dot)} />
                  {data.priority}
                </span>
                <span className={clsx("badge", VIOLATION_TYPE_COLORS[data.violation_type])}>
                  {VIOLATION_TYPE_LABELS[data.violation_type]}
                </span>
                {data.resolved && (
                  <span className="badge bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                    Resolved
                  </span>
                )}
              </div>
              <h1 className="page-title mt-2">{data.title}</h1>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Detected {formatRelativeTime(data.detected_at)}
              </p>
            </div>
          </div>

          <section>
            <h2 className="section-title mb-3">Identity</h2>
            <div className="card p-5">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {data.identity_display_name}
                </span>
                <span className={clsx("badge", IDENTITY_TYPE_COLORS[data.identity_type] ?? "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300")}>
                  {data.identity_type}
                </span>
              </div>
              <p className="mt-1 text-xs font-mono text-slate-500 dark:text-slate-400">
                ID: {data.identity_id}
              </p>
            </div>
          </section>

          <section>
            <h2 className="section-title mb-3">Description</h2>
            <div className="card p-5">
              <p className="text-sm text-slate-700 dark:text-slate-300">
                {data.description}
              </p>
            </div>
          </section>

          {data.affected_roles.length > 0 && (
            <section>
              <h2 className="section-title mb-3">Affected Roles</h2>
              <div className="card p-5">
                <div className="flex flex-wrap gap-2">
                  {data.affected_roles.map((role) => (
                    <span
                      key={role}
                      className="inline-flex rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                    >
                      {role}
                    </span>
                  ))}
                </div>
              </div>
            </section>
          )}

          <section>
            <h2 className="section-title mb-3">Remediation Steps</h2>
            <div className="card overflow-hidden">
              <RemediationSteps steps={data.remediation_steps} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
