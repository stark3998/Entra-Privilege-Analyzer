// frontend/src/components/best-practices/ViolationList.tsx
import { Link } from "react-router-dom";
import clsx from "clsx";
import type { BestPracticeViolation, ViolationType, ViolationPriority } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";

interface ViolationListProps {
  data: BestPracticeViolation[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading: boolean;
}

/** Color map for priority badges -- mirrors SeverityBadge pattern. */
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

const SKELETON_COUNT = 4;

function SkeletonCard() {
  return (
    <div className="card p-5">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="h-5 w-16 animate-pulse rounded-full bg-slate-100 dark:bg-slate-800" />
          <div className="h-5 w-24 animate-pulse rounded-full bg-slate-100 dark:bg-slate-800" />
        </div>
        <div className="h-4 w-64 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
        <div className="h-3 w-48 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
        <div className="h-3 w-full animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </div>
    </div>
  );
}

/**
 * Card-based list of best practice violations with priority badges,
 * violation type tags, identity info, loading skeletons, and pagination.
 */
export function ViolationList({
  data,
  total,
  page,
  pageSize,
  onPageChange,
  isLoading,
}: ViolationListProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: SKELETON_COUNT }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <EmptyState
        title="No violations found"
        description="No best practice violations detected. Run an evaluation to check compliance."
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
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      {data.map((violation) => {
        const pColor = PRIORITY_COLORS[violation.priority];
        return (
          <div key={violation.id} className="card-interactive p-5">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className={clsx("badge capitalize", pColor.bg)}>
                  <span className={clsx("h-1.5 w-1.5 rounded-full", pColor.dot)} />
                  {violation.priority}
                </span>
                <span className={clsx("badge", VIOLATION_TYPE_COLORS[violation.violation_type])}>
                  {VIOLATION_TYPE_LABELS[violation.violation_type]}
                </span>
                {violation.resolved && (
                  <span className="badge bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                    Resolved
                  </span>
                )}
              </div>

              <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                {violation.title}
              </h3>

              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  {violation.identity_display_name}
                </span>
                <span className={clsx("badge", IDENTITY_TYPE_COLORS[violation.identity_type] ?? "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300")}>
                  {violation.identity_type}
                </span>
              </div>

              <p className="text-sm text-slate-500 dark:text-slate-400">
                {violation.description}
              </p>

              <Link to={`/best-practices/${violation.id}`} className="btn-primary inline-flex text-xs">
                View Details
              </Link>
            </div>
          </div>
        );
      })}

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
