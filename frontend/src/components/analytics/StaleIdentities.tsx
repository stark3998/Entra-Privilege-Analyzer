import { useNavigate } from "react-router-dom";

interface StaleIdentitiesProps {
  counts: Record<string, number>;
}

const LABELS: { key: string; label: string; color: string }[] = [
  { key: "30d", label: "30+ days", color: "#f59e0b" },
  { key: "60d", label: "60+ days", color: "#f97316" },
  { key: "90d", label: "90+ days", color: "#ef4444" },
];

export function StaleIdentities({ counts }: StaleIdentitiesProps) {
  const navigate = useNavigate();
  const maxCount = Math.max(1, ...Object.values(counts));

  return (
    <div
      onClick={() => navigate("../identities")}
      className="card-interactive cursor-pointer p-6"
    >
      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
        Stale Identities
      </p>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        Identities with no observed activity
      </p>
      <div className="mt-4 space-y-3">
        {LABELS.map(({ key, label, color }) => {
          const val = counts[key] ?? 0;
          const pct = (val / maxCount) * 100;
          return (
            <div key={key}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-medium text-slate-600 dark:text-slate-400">
                  {label}
                </span>
                <span className="font-bold tabular-nums text-slate-700 dark:text-slate-300">
                  {val.toLocaleString()}
                </span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-full rounded-md transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex items-center gap-1 text-xs font-medium text-brand-600 dark:text-brand-400">
        <span>View identities</span>
        <svg
          className="h-3 w-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 5l7 7-7 7"
          />
        </svg>
      </div>
    </div>
  );
}
