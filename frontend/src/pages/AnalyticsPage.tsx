import { useState } from "react";
import clsx from "clsx";
import { useAnalytics } from "@/api/hooks";
import { Tooltip } from "@/components/common/Tooltip";
import { KpiStrip } from "@/components/analytics/KpiStrip";
import { ActivitySparkline } from "@/components/analytics/ActivitySparkline";
import { HorizontalBarChart } from "@/components/analytics/HorizontalBarChart";
import { DonutChart } from "@/components/analytics/DonutChart";
import { MostActiveIdentities } from "@/components/analytics/MostActiveIdentities";
import { TopResources } from "@/components/analytics/TopResources";
import { PermissionUtilization } from "@/components/analytics/PermissionUtilization";
import { OverprivilegedCard } from "@/components/analytics/OverprivilegedCard";
import { StaleIdentities } from "@/components/analytics/StaleIdentities";
import { RecentDriftActivity } from "@/components/analytics/RecentDriftActivity";
import { PimSessionWidget } from "@/components/analytics/PimSessionWidget";

type TimeRange = 7 | 30 | 90;

const TIME_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: 7, label: "7d" },
  { value: 30, label: "30d" },
  { value: 90, label: "90d" },
];

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

function SectionHeader({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mb-4 mt-2">
      <h2 className="text-sm font-bold text-slate-800 dark:text-slate-200">
        {title}
      </h2>
      <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
    </div>
  );
}

const SOURCE_COLORS: Record<string, string> = {
  audit_log: "#6366f1",
  sign_in_log: "#8b5cf6",
  activity_log: "#a78bfa",
};

const VIOLATION_TYPE_LABELS: Record<string, string> = {
  stale_identity: "Stale Identity",
  permanent_admin: "Permanent Admin",
  no_pim: "No PIM",
  sp_credential_expiry: "Credential Expiry",
  separation_of_duties: "SoD Violation",
  overprivileged: "Overprivileged",
  mfa_gap: "MFA Gap",
  role_assignable_group: "Role-Assignable Group",
};

export function AnalyticsPage() {
  const [days, setDays] = useState<TimeRange>(30);
  const { data, isLoading, isError } = useAnalytics(days);

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-subtitle">
            Activity, permission, and security posture insights
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Tooltip content="Time range for activity-based metrics">
            <svg
              className="h-3.5 w-3.5 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </Tooltip>
          <div className="flex gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
            {TIME_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setDays(opt.value)}
                className={clsx(
                  "rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
                  days === opt.value
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isError && (
        <div className="card border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
          Failed to load analytics data. Please try again later.
        </div>
      )}

      {/* KPI Strip */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {[1, 2, 3, 4, 5].map((i) => (
            <SkeletonCard key={i} className="!p-4" />
          ))}
        </div>
      ) : data ? (
        <KpiStrip
          items={[
            {
              label: "Total Actions",
              value: data.total_actions.toLocaleString(),
              sub: `Last ${days} days`,
            },
            {
              label: "Active Identities",
              value: data.unique_active_identities.toLocaleString(),
              sub: "Unique actors observed",
            },
            {
              label: "Avg Actions / Identity",
              value: data.avg_actions_per_identity.toFixed(1),
            },
            {
              label: "Failure Rate",
              value: `${data.failed_action_pct.toFixed(1)}%`,
              sub:
                data.failed_action_pct > 5
                  ? "Above normal threshold"
                  : "Within normal range",
            },
            {
              label: "New Identities",
              value: data.new_identities_count.toLocaleString(),
              sub: `Detected in last ${days}d`,
            },
          ]}
        />
      ) : null}

      {/* Activity Sparkline */}
      {isLoading ? (
        <SkeletonCard className="h-24" />
      ) : data ? (
        <div className="card px-6 py-4">
          <p className="mb-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
            Daily Activity Volume
          </p>
          <ActivitySparkline data={data.daily_action_counts} />
        </div>
      ) : null}

      {/* ===== Activity Analytics Section ===== */}
      <SectionHeader
        title="Activity Analytics"
        subtitle="What actions are being performed, by whom, and on what"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : data ? (
          <>
            <div className="card p-6">
              <div className="mb-4 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Top Actions
                </h3>
                <Tooltip content="Most frequently performed actions in the selected period">
                  <svg
                    className="h-3.5 w-3.5 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </Tooltip>
              </div>
              <HorizontalBarChart
                data={data.top_actions.map((a) => ({
                  label: a.action,
                  value: a.count,
                }))}
                color="#6366f1"
              />
            </div>

            <div className="card p-6">
              <div className="mb-4 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Most Active Identities
                </h3>
                <Tooltip content="Identities with the highest action count in the selected period">
                  <svg
                    className="h-3.5 w-3.5 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </Tooltip>
              </div>
              <MostActiveIdentities identities={data.most_active_identities} />
            </div>
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : data ? (
          <>
            <div className="card p-6">
              <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Actions by Source
              </h3>
              <DonutChart
                segments={Object.entries(data.actions_by_source).map(
                  ([key, val]) => ({
                    label: key.replace(/_/g, " "),
                    value: val,
                    color: SOURCE_COLORS[key] ?? "#94a3b8",
                  }),
                )}
                centerValue={data.total_actions.toLocaleString()}
                centerLabel="total"
              />
            </div>

            <div className="card p-6">
              <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Success vs Failure
              </h3>
              <DonutChart
                segments={[
                  {
                    label: "Success",
                    value: data.success_vs_failure["success"] ?? 0,
                    color: "#10b981",
                  },
                  {
                    label: "Failure",
                    value: data.success_vs_failure["failure"] ?? 0,
                    color: "#ef4444",
                  },
                ]}
                centerValue={`${(100 - data.failed_action_pct).toFixed(0)}%`}
                centerLabel="success"
              />
            </div>

            <div className="card p-6">
              <div className="mb-4 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Top Resources
                </h3>
                <Tooltip content="Most frequently targeted resources">
                  <svg
                    className="h-3.5 w-3.5 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </Tooltip>
              </div>
              <TopResources resources={data.top_resources} />
            </div>
          </>
        ) : null}
      </div>

      {/* ===== Permission Analytics Section ===== */}
      <SectionHeader
        title="Permission Analytics"
        subtitle="Role distribution, privilege utilization, and overprivilege"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : data ? (
          <>
            <div className="card p-6">
              <div className="mb-4 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Most Assigned Roles
                </h3>
                <Tooltip content="Top directory roles by assignment count across all identities">
                  <svg
                    className="h-3.5 w-3.5 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </Tooltip>
              </div>
              <HorizontalBarChart
                data={data.top_roles.map((r) => ({
                  label: r.role_name,
                  value: r.count,
                }))}
                color="#8b5cf6"
              />
            </div>

            <div className="card p-6">
              <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Permission Utilization
              </h3>
              <PermissionUtilization
                used={data.permission_utilization.used}
                unused={data.permission_utilization.unused}
              />
            </div>
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : data ? (
          <>
            <div className="card p-6">
              <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Permanent vs PIM-Eligible Roles
              </h3>
              <DonutChart
                segments={[
                  {
                    label: "Permanent",
                    value: data.permanent_vs_pim.permanent,
                    color: "#f59e0b",
                  },
                  {
                    label: "PIM / Time-bound",
                    value: data.permanent_vs_pim.pim,
                    color: "#10b981",
                  },
                ]}
                centerValue={`${data.permanent_vs_pim.permanent + data.permanent_vs_pim.pim}`}
                centerLabel="total roles"
              />
            </div>

            <OverprivilegedCard count={data.overprivileged_count} />
          </>
        ) : null}
      </div>

      {/* ===== Security Posture Section ===== */}
      <SectionHeader
        title="Security Posture"
        subtitle="Policy violations, stale accounts, and drift activity"
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {isLoading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : data ? (
          <>
            <div className="card p-6">
              <div className="mb-4 flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Violation Breakdown
                </h3>
                <Tooltip content="Unresolved best practice violations by category">
                  <svg
                    className="h-3.5 w-3.5 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </Tooltip>
              </div>
              <HorizontalBarChart
                data={Object.entries(data.violations_by_type).map(
                  ([key, val]) => ({
                    label: VIOLATION_TYPE_LABELS[key] ?? key,
                    value: val,
                  }),
                )}
                color="#ef4444"
              />
            </div>

            <StaleIdentities counts={data.stale_identity_counts} />
          </>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-1">
        {isLoading ? (
          <SkeletonCard />
        ) : data ? (
          <div className="card p-6">
            <div className="mb-4 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                Recent Drift Activity
              </h3>
              <Tooltip content="Latest drift alerts detected across all identities">
                <svg
                  className="h-3.5 w-3.5 text-slate-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </Tooltip>
            </div>
            <RecentDriftActivity alerts={data.recent_drift_alerts} />
          </div>
        ) : null}
      </div>

      {/* ===== PIM Session Analytics Section ===== */}
      <SectionHeader
        title="PIM Session Analytics"
        subtitle="Privileged role activation patterns and anomaly detection"
      />

      <PimSessionWidget />
    </div>
  );
}
