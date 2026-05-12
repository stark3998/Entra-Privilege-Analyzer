// frontend/src/pages/RecommendationDetailPage.tsx
import { useParams, useNavigate } from "react-router-dom";
import { useRecommendationDetail } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { RoleDiff } from "@/components/recommendations/RoleDiff";
import { PermissionDelta } from "@/components/recommendations/PermissionDelta";
import { CustomRolePreview } from "@/components/recommendations/CustomRolePreview";
import { ExportPanel } from "@/components/recommendations/ExportPanel";
import { ApiError } from "@/api/client";
import clsx from "clsx";
import type { IdentityType } from "@/api/types";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

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

/** Return text color class based on reduction score. */
function reductionScoreColor(score: number): string {
  if (score > 70) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 30) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function RecommendationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useRecommendationDetail(
    id ?? "",
  );

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate("/recommendations")}
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
        Back to Recommendations
      </button>

      {/* Loading */}
      {isLoading && (
        <LoadingSpinner message="Loading recommendation details..." />
      )}

      {/* Error / 404 */}
      {isError && (
        <EmptyState
          title={
            error instanceof ApiError && error.status === 404
              ? "Recommendation not found"
              : "Failed to load recommendation"
          }
          description={
            error instanceof ApiError && error.status === 404
              ? "No recommendation exists for this identity. Try computing recommendations first."
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
              onClick={() => navigate("/recommendations")}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 dark:bg-brand-500 dark:hover:bg-brand-600"
            >
              Return to Recommendations
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
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
                  {data.identity_display_name}
                </h1>
                <span
                  className={clsx(
                    "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                    TYPE_COLORS[data.identity_type as IdentityType] ??
                      "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                  )}
                >
                  {data.identity_type}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Computed {formatRelativeTime(data.computed_at)}
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Reduction Score
              </p>
              <p
                className={clsx(
                  "mt-1 text-xl font-bold",
                  reductionScoreColor(data.reduction_score),
                )}
              >
                {data.reduction_score}%
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Current Roles
              </p>
              <p className="mt-1 text-xl font-bold text-slate-900 dark:text-white">
                {data.current_roles.length}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Required Permissions
              </p>
              <p className="mt-1 text-xl font-bold text-emerald-600 dark:text-emerald-400">
                {data.permission_gaps.filter((g) => g.is_used).length}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Excess Permissions
              </p>
              <p className="mt-1 text-xl font-bold text-red-600 dark:text-red-400">
                {data.permission_gaps.filter((g) => !g.is_used).length}
              </p>
            </div>
          </div>

          {/* Role Diff */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">
              Role Comparison
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <RoleDiff
                currentRoles={data.current_roles}
                bestBuiltinMatch={data.best_builtin_match}
                alternativeBuiltins={data.alternative_builtins}
                customRole={data.custom_role}
              />
            </div>
          </section>

          {/* Permission Delta */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">
              Permission Analysis
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <PermissionDelta permissionGaps={data.permission_gaps} />
            </div>
          </section>

          {/* Custom Role Preview */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">
              Custom Role Definition
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <CustomRolePreview customRole={data.custom_role} />
            </div>
          </section>

          {/* Export Panel */}
          <section>
            <h2 className="mb-4 text-lg font-semibold text-slate-900 dark:text-white">
              Export as Infrastructure as Code
            </h2>
            <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
              <ExportPanel identityId={data.identity_id} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
