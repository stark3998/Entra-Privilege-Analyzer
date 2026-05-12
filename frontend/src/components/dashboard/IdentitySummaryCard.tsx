// frontend/src/components/dashboard/IdentitySummaryCard.tsx

const TYPE_COLORS: Record<string, { dot: string; bar: string }> = {
  User: {
    dot: "bg-blue-500",
    bar: "bg-blue-500",
  },
  ServicePrincipal: {
    dot: "bg-purple-500",
    bar: "bg-purple-500",
  },
  ManagedIdentity: {
    dot: "bg-emerald-500",
    bar: "bg-emerald-500",
  },
  Group: {
    dot: "bg-amber-500",
    bar: "bg-amber-500",
  },
};

const TYPE_LABELS: Record<string, string> = {
  User: "Users",
  ServicePrincipal: "Service Principals",
  ManagedIdentity: "Managed Identities",
  Group: "Groups",
};

interface IdentitySummaryCardProps {
  /** Total number of identities. */
  total: number;
  /** Count per identity type. */
  byType: Record<string, number>;
}

/**
 * Card showing total identity count with a breakdown by type
 * and a horizontal stacked bar showing proportions.
 *
 * Usage:
 * ```tsx
 * <IdentitySummaryCard total={1200} byType={{ User: 800, ServicePrincipal: 300, ManagedIdentity: 50, Group: 50 }} />
 * ```
 */
export function IdentitySummaryCard({ total, byType }: IdentitySummaryCardProps) {
  const types = Object.keys(TYPE_COLORS);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
        Total Identities
      </p>
      <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
        {total.toLocaleString()}
      </p>

      {/* Breakdown list */}
      <div className="mt-4 space-y-2">
        {types.map((type) => {
          const count = byType[type] ?? 0;
          const colors = TYPE_COLORS[type];
          return (
            <div key={type} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${colors?.dot ?? "bg-slate-400"}`} />
                <span className="text-slate-600 dark:text-slate-400">
                  {TYPE_LABELS[type] ?? type}
                </span>
              </div>
              <span className="font-medium tabular-nums text-slate-900 dark:text-white">
                {count.toLocaleString()}
              </span>
            </div>
          );
        })}
      </div>

      {/* Stacked bar */}
      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {types.map((type) => {
          const count = byType[type] ?? 0;
          const pct = total > 0 ? (count / total) * 100 : 0;
          const colors = TYPE_COLORS[type];
          return (
            <div
              key={type}
              className={colors?.bar ?? "bg-slate-400"}
              style={{ width: `${pct}%` }}
              title={`${TYPE_LABELS[type] ?? type}: ${count}`}
            />
          );
        })}
      </div>
    </div>
  );
}
