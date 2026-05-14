import { useAccessPathsSummary } from "@/api/hooks";

export function AccessPathSummaryCard() {
  const { data: summary, isLoading } = useAccessPathsSummary();

  if (isLoading) {
    return (
      <div className="animate-pulse rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="h-4 w-40 rounded bg-slate-200 dark:bg-slate-700" />
        <div className="mt-4 h-8 w-20 rounded bg-slate-200 dark:bg-slate-700" />
      </div>
    );
  }

  const total = summary?.total_identities_with_paths ?? 0;
  const critical = summary?.critical_count ?? 0;
  const high = summary?.high_count ?? 0;
  const medium = summary?.medium_count ?? 0;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
      <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
        Privilege Escalation Paths
      </h3>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-2xl font-bold text-slate-900 dark:text-white">{total}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Identities at Risk</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-red-600 dark:text-red-400">{critical}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Critical</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{high}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">High</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{medium}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Medium</p>
        </div>
      </div>
    </div>
  );
}
