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
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { Tooltip } from "@/components/common/Tooltip";
import { MotionStagger, MotionItem } from "@/components/common/motion";
import { useNavigate } from "react-router-dom";
import { useProjectContext } from "@/store/projectContext";

function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card p-6 ${className}`}>
      <div className="skeleton h-4 w-1/3" />
      <div className="skeleton mt-3 h-8 w-1/2" />
      <div className="mt-4 space-y-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-4/5" />
        <div className="skeleton h-3 w-3/5" />
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
  const { project, projectId } = useProjectContext();

  return (
    <div className="space-y-6">
      {/* Hero header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Executive Overview</p>
          <h1 className="page-title mt-1">Dashboard</h1>
          <p className="page-subtitle">
            Least-privilege posture for{" "}
            <span className="font-medium text-slate-600 dark:text-slate-300">
              {project?.target_tenant_name ?? "your tenant"}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate(`/projects/${projectId}/reports`)}
            className="btn-secondary"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Reports
          </button>
          <button
            onClick={() => navigate(`/projects/${projectId}/scan`)}
            className="btn-primary"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Run Scan
          </button>
        </div>
      </div>

      {summaryError && (
        <div className="card border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
          Failed to load dashboard data. Please try again later.
        </div>
      )}

      {/* Row 1: Key metrics */}
      {summaryLoading ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : summary ? (
        <MotionStagger className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <MotionItem>
            <RiskScoreCard score={summary.avg_risk_score} highRiskCount={summary.high_risk_count} />
          </MotionItem>
          <MotionItem>
            <IdentitySummaryCard total={summary.total_identities} byType={summary.identities_by_type} />
          </MotionItem>
          <MotionItem>
            <DriftSummaryCard total={summary.drift_alerts_open} bySeverity={summary.drift_alerts_by_severity} />
          </MotionItem>
        </MotionStagger>
      ) : null}

      {/* Row 2: Compliance + Recommendations */}
      {summaryLoading ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : summary ? (
        <MotionStagger className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <MotionItem>
            <div
              onClick={() => navigate(`/projects/${projectId}/best-practices`)}
              className="card-interactive group h-full p-6"
            >
              <div className="flex items-center gap-6">
                <ComplianceGauge score={summary.compliance_score} size={130} />
                <div>
                  <p className="eyebrow">Best Practice Compliance</p>
                  <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
                    Policy evaluations across all identities
                  </p>
                  <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-brand-600 transition-transform group-hover:translate-x-0.5 dark:text-brand-400">
                    <span>View findings</span>
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </MotionItem>

          <MotionItem>
            <div
              onClick={() => navigate(`/projects/${projectId}/recommendations`)}
              className="card-interactive group h-full p-6"
            >
              <div className="flex items-center gap-2">
                <p className="eyebrow">Role Recommendations</p>
                <Tooltip content="Least-privilege role suggestions based on observed permission usage">
                  <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </Tooltip>
              </div>
              <AnimatedNumber
                value={summary.recommendations_count}
                className="mt-2 block text-4xl font-bold tabular-nums text-slate-900 dark:text-white"
              />
              <div className="mt-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 dark:bg-emerald-950/40">
                  <svg className="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Avg. privilege reduction</p>
                  <p className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                    <AnimatedNumber value={summary.avg_reduction_score} decimals={1} suffix="%" />
                  </p>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-brand-600 transition-transform group-hover:translate-x-0.5 dark:text-brand-400">
                <span>View recommendations</span>
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </MotionItem>
        </MotionStagger>
      ) : null}

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
      {summaryLoading ? (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <TopRiskyIdentities identities={summary?.top_risky_identities ?? []} />
          <AINarrativeCard
            title="Executive Digest"
            content={narrative?.content ?? null}
            isLoading={narrativeLoading}
            onRefresh={() => refreshNarrative.mutate()}
            isRefreshing={refreshNarrative.isPending}
          />
        </div>
      )}
    </div>
  );
}
