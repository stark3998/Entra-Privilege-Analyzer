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
const PRIORITY_COLORS: Record<ViolationPriority, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300",
  info: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
};

/** Color map for violation type badges. */
const VIOLATION_TYPE_COLORS: Record<ViolationType, string> = {
  stale_identity:
    "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300",
  permanent_admin:
    "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  no_pim:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  sp_credential_expiry:
    "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  separation_of_duties:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  overprivileged:
    "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  mfa_gap:
    "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  role_assignable_group:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
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
  User: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  ServicePrincipal:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  ManagedIdentity:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  Group:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
};

export function BestPracticeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useViolationDetail(id ?? "");

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate("/best-practices")}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
      >
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
            d="M15 19l-7-7 7-7"
          />
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
            <button
              onClick={() => navigate("/best-practices")}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600"
            >
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
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize",
                    PRIORITY_COLORS[data.priority],
                  )}
                >
                  {data.priority}
                </span>
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                    VIOLATION_TYPE_COLORS[data.violation_type],
                  )}
                >
                  {VIOLATION_TYPE_LABELS[data.violation_type]}
                </span>
                {data.resolved && (
                  <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                    Resolved
                  </span>
                )}
              </div>
              <h1 className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">
                {data.title}
              </h1>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Detected {formatRelativeTime(data.detected_at)}
              </p>
            </div>
          </div>

          {/* Identity info */}
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-white">
              Identity
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-slate-900 dark:text-white">
                  {data.identity_display_name}
                </span>
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                    IDENTITY_TYPE_COLORS[data.identity_type] ??
                      "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                  )}
                >
                  {data.identity_type}
                </span>
              </div>
              <p className="mt-1 text-xs font-mono text-slate-500 dark:text-slate-400">
                ID: {data.identity_id}
              </p>
            </div>
          </section>

          {/* Description */}
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-white">
              Description
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-sm text-slate-700 dark:text-slate-300">
                {data.description}
              </p>
            </div>
          </section>

          {/* Affected Roles */}
          {data.affected_roles.length > 0 && (
            <section>
              <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-white">
                Affected Roles
              </h2>
              <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
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

          {/* Remediation Steps */}
          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-900 dark:text-white">
              Remediation Steps
            </h2>
            <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
              <RemediationSteps steps={data.remediation_steps} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
