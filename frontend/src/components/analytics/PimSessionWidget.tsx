import { usePimSessionAnalytics, useActivePimSessions } from "@/api/hooks";

export function PimSessionWidget() {
  const { data: analytics, isLoading: analyticsLoading } = usePimSessionAnalytics(30);
  const { data: activeData } = useActivePimSessions();

  const activeCount = activeData?.total ?? 0;
  const total = analytics?.total_sessions ?? 0;
  const anomalyCount = analytics?.sessions_with_anomalies ?? 0;
  const avgDuration = analytics?.avg_session_duration_minutes ?? 0;

  if (analyticsLoading) {
    return (
      <div className="animate-pulse rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="h-4 w-32 rounded bg-slate-200 dark:bg-slate-700" />
        <div className="mt-4 h-8 w-20 rounded bg-slate-200 dark:bg-slate-700" />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
      <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
        PIM Sessions (30d)
      </h3>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{total}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Total Sessions</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">{activeCount}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Active Now</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-red-600 dark:text-red-400">{anomalyCount}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">With Anomalies</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">
            {avgDuration < 60 ? `${Math.round(avgDuration)}m` : `${(avgDuration / 60).toFixed(1)}h`}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Avg Duration</p>
        </div>
      </div>

      {/* Top activated roles */}
      {analytics && analytics.top_activated_roles.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">Top Activated Roles</p>
          <div className="mt-1 space-y-1">
            {analytics.top_activated_roles.slice(0, 5).map((r) => (
              <div key={r.role_name} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 dark:text-slate-300 truncate">{r.role_name}</span>
                <span className="ml-2 font-medium text-slate-900 dark:text-white">{r.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
