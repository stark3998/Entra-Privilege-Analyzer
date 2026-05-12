// frontend/src/pages/DashboardPage.tsx
import {
  useDashboardSummary,
  useDashboardTrends,
  useExecutiveNarrative,
  useRefreshNarrative,
} from "@/api/hooks";
import { RiskScoreCard } from "@/components/dashboard/RiskScoreCard";
import { IdentitySummaryCard } from "@/components/dashboard/IdentitySummaryCard";
import { DriftSummaryCard } from "@/components/dashboard/DriftSummaryCard";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { TopRiskyIdentities } from "@/components/dashboard/TopRiskyIdentities";
import { AINarrativeCard } from "@/components/common/AINarrativeCard";
import { ComplianceGauge } from "@/components/best-practices/ComplianceGauge";

function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900 ${className}`}
    >
      <div className="h-4 w-1/3 rounded bg-slate-200 dark:bg-slate-700" />
      <div className="mt-3 h-8 w-1/2 rounded bg-slate-200 dark:bg-slate-700" />
      <div className="mt-4 space-y-2">
        <div className="h-3 w-full rounded bg-slate-200 dark:bg-slate-700" />
        <div className="h-3 w-4/5 rounded bg-slate-200 dark:bg-slate-700" />
        <div className="h-3 w-3/5 rounded bg-slate-200 dark:bg-slate-700" />
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useDashboardSummary();
  const { data: trends, isLoading: trendsLoading } = useDashboardTrends();
  const { data: narrative, isLoading: narrativeLoading } = useExecutiveNarrative();
  const refreshNarrative = useRefreshNarrative();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Overview of your Entra ID permissions posture
        </p>
      </div>

      {/* Error state */}
      {summaryError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load dashboard data. Please try again later.
        </div>
      )}

      {/* Row 1: Risk Score, Identity Summary, Drift Summary */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {summaryLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : summary ? (
          <>
            <RiskScoreCard
              score={summary.avg_risk_score}
              highRiskCount={summary.high_risk_count}
            />
            <IdentitySummaryCard
              total={summary.total_identities}
              byType={summary.identities_by_type}
            />
            <DriftSummaryCard
              total={summary.drift_alerts_open}
              bySeverity={summary.drift_alerts_by_severity}
            />
          </>
        ) : null}
      </div>

      {/* Row 2: Compliance Score + Recommendations Summary */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {summaryLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : summary ? (
          <>
            {/* Compliance Score */}
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-6">
                <ComplianceGauge score={summary.compliance_score} size={140} />
                <div>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    Best Practice Compliance
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Based on policy evaluations across all identities
                  </p>
                </div>
              </div>
            </div>

            {/* Recommendations Summary */}
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                Role Recommendations
              </p>
              <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
                {summary.recommendations_count.toLocaleString()}
              </p>
              <div className="mt-4 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
                  <svg
                    className="h-4 w-4 text-emerald-600 dark:text-emerald-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Avg. Reduction Score
                  </p>
                  <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                    {summary.avg_reduction_score.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>

      {/* Row 3: Trend Chart */}
      {trendsLoading ? (
        <SkeletonCard className="h-[280px]" />
      ) : trends ? (
        <TrendChart
          riskTrend={trends.risk_score_trend}
          driftTrend={trends.drift_alerts_trend}
          actionsTrend={trends.actions_trend}
        />
      ) : null}

      {/* Row 4: Top Risky Identities + AI Narrative */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {summaryLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <TopRiskyIdentities
              identities={summary?.top_risky_identities ?? []}
            />
            <AINarrativeCard
              title="Executive Digest"
              content={narrative?.content ?? null}
              isLoading={narrativeLoading}
              onRefresh={() => refreshNarrative.mutate()}
              isRefreshing={refreshNarrative.isPending}
            />
          </>
        )}
      </div>
    </div>
  );
}
