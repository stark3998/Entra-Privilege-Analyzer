// frontend/src/pages/RecommendationDetailPage.tsx
import { Link, useParams, useNavigate } from "react-router-dom";
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
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionItem, MotionStagger } from "@/components/common/motion";
import { useProjectContext } from "@/store/projectContext";

/** Color map for identity type badges. Matches IdentityDetail. */
const TYPE_COLORS: Record<string, { bg: string; dot: string }> = {
  User: { bg: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300", dot: "bg-blue-500" },
  ServicePrincipal: { bg: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300", dot: "bg-purple-500" },
  ManagedIdentity: { bg: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300", dot: "bg-emerald-500" },
  Group: { bg: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300", dot: "bg-amber-500" },
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
  const { projectId } = useProjectContext();
  const { data, isLoading, isError, error } = useRecommendationDetail(
    id ?? "",
  );

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => navigate(`/projects/${projectId}/recommendations`)}
        className="btn-ghost"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
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
            <button type="button" onClick={() => navigate(`/projects/${projectId}/recommendations`)} className="btn-primary">
              Return to Recommendations
            </button>
          }
        />
      )}

      {/* Detail view */}
      {data && (
        <div className="space-y-8">
          {/* Header */}
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="eyebrow">Recommendation Detail</p>
              <div className="flex items-center gap-3">
                <h1 className="page-title mt-1">{data.identity_display_name}</h1>
                {(() => {
                  const c = TYPE_COLORS[data.identity_type as IdentityType];
                  return (
                    <span className={clsx("badge", c?.bg ?? "bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300")}>
                      <span className={clsx("h-1.5 w-1.5 rounded-full", c?.dot ?? "bg-slate-400")} />
                      {data.identity_type}
                    </span>
                  );
                })()}
              </div>
              <p className="page-subtitle">
                Computed {formatRelativeTime(data.computed_at)}
              </p>
            </div>
          </div>

          <MotionStagger className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MotionItem className="card p-4">
              <p className="eyebrow">Reduction Score</p>
              <AnimatedNumber value={data.reduction_score} suffix="%" className={clsx("mt-1 block text-xl font-bold", reductionScoreColor(data.reduction_score))} />
            </MotionItem>
            <MotionItem className="card p-4">
              <p className="eyebrow">Current Roles</p>
              <AnimatedNumber value={data.current_roles.length} className="mt-1 block text-xl font-bold text-slate-900 dark:text-white" />
            </MotionItem>
            <MotionItem className="card p-4">
              <p className="eyebrow">Required Permissions</p>
              <AnimatedNumber value={data.permission_gaps.filter((g) => g.is_used).length} className="mt-1 block text-xl font-bold text-emerald-600 dark:text-emerald-400" />
            </MotionItem>
            <MotionItem className="card p-4">
              <p className="eyebrow">Excess Permissions</p>
              <AnimatedNumber value={data.permission_gaps.filter((g) => !g.is_used).length} className="mt-1 block text-xl font-bold text-red-600 dark:text-red-400" />
            </MotionItem>
          </MotionStagger>

          <section className="card p-5">
            <h2 className="section-title">Related</h2>
            <div className="mt-3 space-y-1">
              <Link
                to={`/projects/${projectId}/identities/${data.identity_id}`}
                className="group flex items-center justify-between rounded-xl px-3 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/60"
              >
                <span>
                  <span className="block text-sm font-medium text-slate-900 dark:text-white">Identity profile</span>
                  <span className="block text-xs text-slate-500 dark:text-slate-400">{data.identity_display_name}</span>
                </span>
                <span className="text-slate-400 transition-transform group-hover:translate-x-0.5">›</span>
              </Link>
            </div>
          </section>

          <section>
            <h2 className="section-title mb-4">Role Comparison</h2>
            <div className="card p-5">
              <RoleDiff
                currentRoles={data.current_roles}
                bestBuiltinMatch={data.best_builtin_match}
                alternativeBuiltins={data.alternative_builtins}
                customRole={data.custom_role}
              />
            </div>
          </section>

          <section>
            <h2 className="section-title mb-4">Permission Analysis</h2>
            <div className="card p-5">
              <PermissionDelta permissionGaps={data.permission_gaps} />
            </div>
          </section>

          <section>
            <h2 className="section-title mb-4">Custom Role Definition</h2>
            <div className="card p-5">
              <CustomRolePreview customRole={data.custom_role} />
            </div>
          </section>

          <section>
            <h2 className="section-title mb-4">Export as Infrastructure as Code</h2>
            <div className="card p-5">
              <ExportPanel identityId={data.identity_id} />
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
