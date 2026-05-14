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
import { Tooltip } from "@/components/common/Tooltip";
import { useNavigate } from "react-router-dom";

function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card animate-pulse p-6 ${className}`}>
      <div className="h-4 w-1/3 rounded bg-slate-100 dark:bg-slate-800" />
      <div className="mt-3 h-8 w-1/2 rounded bg-slate-100 dark:bg-slate-800" />
      <div className="mt-4 space-y-2">
        <div className="h-3 w-full rounded bg-slate-100 dark:bg-slate-800" />
        <div className="h-3 w-4/5 rounded bg-slate-100 dark:bg-slate-800" />
        <div className="h-3 w-3/5 rounded bg-slate-100 dark:bg-slate-800" />
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: summary, isLoading: summaryLoading, isError: summaryError } = useDashboardSummary();
  const { data: trends, isLoading: trendsLoading } = useDashboardTrends();
  const { data: narrative, isLoading: narrativeLoading } = useExecutiveNarrative();
  const refreshNarrative = useRefreshNarrative();
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            Overview of your Entra ID permissions posture
          </p>
        </div>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Last synced: <span className="font-medium text-slate-500 dark:text-slate-400">just now</span>
        </p>
      </div>

      {summaryError && (
        <div className="card border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load dashboard data. Please try again later.
        </div>
      )}

      {/* Row 1: Key metrics */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {summaryLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : summary ? (
          <>
            <RiskScoreCard score={summary.avg_risk_score} highRiskCount={summary.high_risk_count} />
            <IdentitySummaryCard total={summary.total_identities} byType={summary.identities_by_type} />
            <DriftSummaryCard total={summary.drift_alerts_open} bySeverity={summary.drift_alerts_by_severity} />
          </>
        ) : null}
      </div>

      {/* Row 2: Compliance + Recommendations */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {summaryLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : summary ? (
          <>
            {/* Compliance */}
            <div
              onClick={() => navigate("../best-practices")}
              className="card-interactive p-6"
            >
              <div className="flex items-center gap-6">
                <ComplianceGauge score={summary.compliance_score} size={130} />
                <div>
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    Best Practice Compliance
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Based on policy evaluations across all identities
                  </p>
                  <div className="mt-3 flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
                    <span>View details</span>
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* Recommendations */}
            <div
              onClick={() => navigate("../recommendations")}
              className="card-interactive p-6"
            >
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Role Recommendations
                </p>
                <Tooltip content="Least-privilege role suggestions based on observed permission usage">
                  <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </Tooltip>
              </div>
              <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
                {summary.recommendations_count.toLocaleString()}
              </p>
              <div className="mt-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 dark:bg-emerald-900/20">
                  <svg className="h-4 w-4 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Avg. Reduction Score</p>
                  <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                    {summary.avg_reduction_score.toFixed(1)}%
                  </p>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
                <span>View recommendations</span>
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
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

      {/* Row 4: Top Risky + AI Narrative */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {summaryLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <TopRiskyIdentities identities={summary?.top_risky_identities ?? []} />
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
