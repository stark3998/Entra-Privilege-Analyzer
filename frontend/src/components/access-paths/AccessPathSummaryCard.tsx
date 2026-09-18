import { useAccessPathsSummary } from "@/api/hooks";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionItem, MotionStagger } from "@/components/common/motion";

export function AccessPathSummaryCard() {
  const { data: summary, isLoading } = useAccessPathsSummary();

  if (isLoading) {
    return (
      <div className="card p-6">
        <div className="skeleton h-4 w-40" />
        <div className="skeleton mt-4 h-8 w-20" />
      </div>
    );
  }

  const total = summary?.total_identities_with_paths ?? 0;
  const critical = summary?.critical_count ?? 0;
  const high = summary?.high_count ?? 0;
  const medium = summary?.medium_count ?? 0;

  return (
    <div className="card p-6">
      <p className="eyebrow">Path Exposure</p>
      <h3 className="section-title mt-1">
        Privilege Escalation Paths
      </h3>

      <MotionStagger className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MotionItem>
          <AnimatedNumber value={total} className="block text-2xl font-bold tabular-nums text-slate-900 dark:text-white" />
          <p className="text-xs text-slate-500 dark:text-slate-400">Identities at Risk</p>
        </MotionItem>
        <MotionItem>
          <AnimatedNumber value={critical} className="block text-2xl font-bold tabular-nums text-red-600 dark:text-red-400" />
          <p className="text-xs text-slate-500 dark:text-slate-400">Critical</p>
        </MotionItem>
        <MotionItem>
          <AnimatedNumber value={high} className="block text-2xl font-bold tabular-nums text-orange-600 dark:text-orange-400" />
          <p className="text-xs text-slate-500 dark:text-slate-400">High</p>
        </MotionItem>
        <MotionItem>
          <AnimatedNumber value={medium} className="block text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400" />
          <p className="text-xs text-slate-500 dark:text-slate-400">Medium</p>
        </MotionItem>
      </MotionStagger>
    </div>
  );
}
