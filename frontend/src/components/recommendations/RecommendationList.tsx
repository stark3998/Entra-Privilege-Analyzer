// frontend/src/components/recommendations/RecommendationList.tsx
import { Link } from "react-router-dom";
import clsx from "clsx";
import type { RoleRecommendation, IdentityType } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";

interface RecommendationListProps {
  data: RoleRecommendation[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading: boolean;
}

/** Color map for identity type badges. Matches IdentityDetail. */
const TYPE_COLORS: Record<string, string> = {
  User: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  ServicePrincipal:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  ManagedIdentity:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  Group:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
};

const SKELETON_COUNT = 4;

/** Return color classes based on reduction score thresholds. */
function reductionColor(score: number): {
  stroke: string;
  text: string;
  bg: string;
} {
  if (score > 70)
    return {
      stroke: "text-emerald-500",
      text: "text-emerald-700 dark:text-emerald-400",
      bg: "bg-emerald-50 dark:bg-emerald-900/20",
    };
  if (score >= 30)
    return {
      stroke: "text-amber-500",
      text: "text-amber-700 dark:text-amber-400",
      bg: "bg-amber-50 dark:bg-amber-900/20",
    };
  return {
    stroke: "text-red-500",
    text: "text-red-700 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-900/20",
  };
}

/**
 * Circular progress indicator rendered as an SVG ring.
 * Shows the reduction_score as a percentage.
 */
function CircularProgress({
  score,
  size = 56,
}: {
  score: number;
  size?: number;
}) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const colors = reductionColor(score);

  return (
    <div className={clsx("relative flex-shrink-0", colors.bg, "rounded-full p-1")}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={4}
          className="text-slate-200 dark:text-slate-700"
        />
        {/* Progress arc */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={4}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={colors.stroke}
        />
      </svg>
      <span
        className={clsx(
          "absolute inset-0 flex items-center justify-center text-xs font-bold",
          colors.text,
        )}
      >
        {score}%
      </span>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center gap-4">
        <div className="h-14 w-14 animate-pulse rounded-full bg-slate-200 dark:bg-slate-700" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-48 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
          <div className="h-3 w-32 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
          <div className="h-3 w-64 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
        </div>
      </div>
    </div>
  );
}

/**
 * Card-based list of role recommendations with circular reduction scores,
 * identity badges, loading skeletons, empty state, and pagination.
 */
export function RecommendationList({
  data,
  total,
  page,
  pageSize,
  onPageChange,
  isLoading,
}: RecommendationListProps) {
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
        title="No recommendations computed yet"
        description="Click Compute to analyze permissions and generate least-privilege role recommendations."
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
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
        }
      />
    );
  }

  const excessCount = (rec: RoleRecommendation): number =>
    rec.permission_gaps.filter((g) => !g.is_used).length;

  const recommendedSummary = (rec: RoleRecommendation): string => {
    if (rec.best_builtin_match) {
      return `1 built-in (${rec.best_builtin_match.role_name})`;
    }
    return "1 custom role";
  };

  return (
    <div className="space-y-4">
      {data.map((rec) => (
        <div
          key={rec.id}
          className="rounded-xl border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900"
        >
          <div className="flex items-center gap-4">
            {/* Reduction score */}
            <CircularProgress score={rec.reduction_score} />

            {/* Content */}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                  {rec.identity_display_name}
                </h3>
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                    TYPE_COLORS[rec.identity_type as IdentityType] ??
                      "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                  )}
                >
                  {rec.identity_type}
                </span>
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                <span>
                  {rec.current_roles.length} role{rec.current_roles.length !== 1 ? "s" : ""}{" "}
                  &rarr; {recommendedSummary(rec)}
                </span>
                <span className="text-red-600 dark:text-red-400">
                  {excessCount(rec)} excess permission{excessCount(rec) !== 1 ? "s" : ""}
                </span>
              </div>
            </div>

            {/* View Details link */}
            <Link
              to={`/recommendations/${rec.identity_id}`}
              className="flex-shrink-0 rounded-lg bg-brand-600 px-3.5 py-2 text-xs font-medium text-white transition-colors hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600"
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
