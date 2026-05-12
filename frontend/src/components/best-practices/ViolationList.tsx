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

const SKELETON_COUNT = 4;

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="h-5 w-16 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
          <div className="h-5 w-24 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
        </div>
        <div className="h-4 w-64 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
        <div className="h-3 w-48 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
        <div className="h-3 w-full animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
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
      {data.map((violation) => (
        <div
          key={violation.id}
          className="rounded-xl border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="space-y-3">
            {/* Badges row */}
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={clsx(
                  "inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                  PRIORITY_COLORS[violation.priority],
                )}
              >
                {violation.priority}
              </span>
              <span
                className={clsx(
                  "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                  VIOLATION_TYPE_COLORS[violation.violation_type],
                )}
              >
                {VIOLATION_TYPE_LABELS[violation.violation_type]}
              </span>
              {violation.resolved && (
                <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                  Resolved
                </span>
              )}
            </div>

            {/* Title */}
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              {violation.title}
            </h3>

            {/* Identity info */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-600 dark:text-slate-400">
                {violation.identity_display_name}
              </span>
              <span
                className={clsx(
                  "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                  IDENTITY_TYPE_COLORS[violation.identity_type] ??
                    "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                )}
              >
                {violation.identity_type}
              </span>
            </div>

            {/* Description */}
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {violation.description}
            </p>

            {/* View Details link */}
            <Link
              to={`/best-practices/${violation.id}`}
              className="inline-flex rounded-lg bg-brand-600 px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600"
            >
              View Details
            </Link>
          </div>
        </div>
      ))}

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
                "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                page <= 1
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
              )}
            >
              Prev
            </button>
            <span className="px-2 text-xs text-slate-500 dark:text-slate-400">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className={clsx(
                "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                page >= totalPages
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
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
