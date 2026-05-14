import clsx from "clsx";

interface ResourceItem {
  resource: string;
  resource_type: string;
  count: number;
}

interface TopResourcesProps {
  resources: ResourceItem[];
}

const TYPE_COLORS: Record<string, string> = {
  Application:
    "bg-violet-50 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300",
  User: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  Group:
    "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  Device:
    "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
};

export function TopResources({ resources }: TopResourcesProps) {
  if (resources.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
        No resource data
      </p>
    );
  }

  const maxCount = Math.max(1, ...resources.map((r) => r.count));

  return (
    <div className="space-y-1.5">
      {resources.slice(0, 10).map((res, idx) => (
        <div
          key={`${res.resource}-${idx}`}
          className="flex items-center gap-3 rounded-xl px-3 py-2"
        >
          <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded text-[10px] font-bold tabular-nums text-slate-400">
            {idx + 1}
          </span>

          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-slate-700 dark:text-slate-300">
              {res.resource || "(unnamed)"}
            </p>
            {res.resource_type && (
              <span
                className={clsx(
                  "mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium",
                  TYPE_COLORS[res.resource_type] ??
                    "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                )}
              >
                {res.resource_type}
              </span>
            )}
          </div>

          <div className="flex flex-shrink-0 items-center gap-2">
            <div className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-violet-500 transition-all"
                style={{ width: `${(res.count / maxCount) * 100}%` }}
              />
            </div>
            <span className="w-10 text-right text-xs font-bold tabular-nums text-slate-700 dark:text-slate-300">
              {res.count.toLocaleString()}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
