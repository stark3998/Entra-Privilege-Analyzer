// frontend/src/components/recommendations/PermissionDelta.tsx
import clsx from "clsx";
import type { PermissionGap } from "@/api/types";

interface PermissionDeltaProps {
  permissionGaps: PermissionGap[];
}

/** Color classes for risk weight badges. */
const RISK_COLORS: Record<string, string> = {
  low: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400",
  critical: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
};

function PermissionRow({
  gap,
  index,
}: {
  gap: PermissionGap;
  index: number;
}) {
  return (
    <div
      className="flex items-center justify-between rounded-lg px-3 py-2 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40"
      style={{ animationDelay: `${index * 30}ms` }}
    >
      <span className="min-w-0 truncate text-sm text-slate-800 dark:text-slate-200" title={gap.permission}>
        {gap.permission}
      </span>
      <span
        className={clsx(
          "ml-2 inline-flex flex-shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase",
          RISK_COLORS[gap.risk_weight] ?? RISK_COLORS.low,
        )}
      >
        {gap.risk_weight}
      </span>
    </div>
  );
}

/**
 * Permission delta visualization showing required (used) vs. excess (unused) permissions.
 * Each permission displays its risk weight badge.
 *
 * Usage:
 * ```tsx
 * <PermissionDelta permissionGaps={rec.permission_gaps} />
 * ```
 */
export function PermissionDelta({ permissionGaps }: PermissionDeltaProps) {
  const required = permissionGaps.filter((g) => g.is_used);
  const excess = permissionGaps.filter((g) => !g.is_used);
  const total = permissionGaps.length;
  const requiredPct = total > 0 ? Math.round((required.length / total) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="space-y-2">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          <span className="font-semibold text-slate-900 dark:text-white">
            {required.length}
          </span>{" "}
          of{" "}
          <span className="font-semibold text-slate-900 dark:text-white">
            {total}
          </span>{" "}
          permissions are needed
        </p>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-red-200 dark:bg-red-900/30">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-500 dark:bg-emerald-400"
            style={{ width: `${requiredPct}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-slate-400 dark:text-slate-500">
          <span>
            {required.length} required ({requiredPct}%)
          </span>
          <span>
            {excess.length} excess ({100 - requiredPct}%)
          </span>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Required permissions */}
        <div>
          <div className="mb-2 flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Required Permissions ({required.length})
            </h4>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 dark:border-emerald-800/40 dark:bg-emerald-900/10">
            {required.length === 0 ? (
              <p className="p-4 text-center text-xs text-slate-400 dark:text-slate-500">
                No required permissions identified
              </p>
            ) : (
              <div className="divide-y divide-emerald-100 dark:divide-emerald-800/30">
                {required.map((gap, idx) => (
                  <PermissionRow
                    key={gap.permission}
                    gap={gap}
                    index={idx}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Excess permissions */}
        <div>
          <div className="mb-2 flex items-center gap-2">
            <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Excess Permissions ({excess.length})
            </h4>
          </div>
          <div className="rounded-xl border border-red-200 bg-red-50/50 dark:border-red-800/40 dark:bg-red-900/10">
            {excess.length === 0 ? (
              <p className="p-4 text-center text-xs text-slate-400 dark:text-slate-500">
                No excess permissions -- already least-privilege
              </p>
            ) : (
              <div className="divide-y divide-red-100 dark:divide-red-800/30">
                {excess.map((gap, idx) => (
                  <PermissionRow
                    key={gap.permission}
                    gap={gap}
                    index={idx}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
