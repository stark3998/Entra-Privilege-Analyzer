import { useNavigate } from "react-router-dom";
import { Tooltip } from "@/components/common/Tooltip";

const TYPE_COLORS: Record<string, { dot: string; bar: string }> = {
  User: { dot: "bg-blue-500", bar: "bg-blue-500" },
  ServicePrincipal: { dot: "bg-purple-500", bar: "bg-purple-500" },
  ManagedIdentity: { dot: "bg-emerald-500", bar: "bg-emerald-500" },
  Group: { dot: "bg-amber-500", bar: "bg-amber-500" },
};

const TYPE_LABELS: Record<string, string> = {
  User: "Users",
  ServicePrincipal: "Service Principals",
  ManagedIdentity: "Managed Identities",
  Group: "Groups",
};

interface IdentitySummaryCardProps {
  total: number;
  byType: Record<string, number>;
}

export function IdentitySummaryCard({ total, byType }: IdentitySummaryCardProps) {
  const navigate = useNavigate();
  const types = Object.keys(TYPE_COLORS);

  return (
    <div
      onClick={() => navigate("/identities")}
      className="card-interactive p-6"
    >
      <div className="flex items-center gap-2">
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Total Identities
        </p>
        <Tooltip content="All Entra ID identities being monitored across your tenant">
          <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </Tooltip>
      </div>
      <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
        {total.toLocaleString()}
      </p>

      <div className="mt-4 space-y-2">
        {types.map((type) => {
          const count = byType[type] ?? 0;
          const colors = TYPE_COLORS[type];
          return (
            <div key={type} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${colors?.dot ?? "bg-slate-400"}`} />
                <span className="text-slate-500 dark:text-slate-400">
                  {TYPE_LABELS[type] ?? type}
                </span>
              </div>
              <span className="font-semibold tabular-nums text-slate-900 dark:text-white">
                {count.toLocaleString()}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {types.map((type) => {
          const count = byType[type] ?? 0;
          const pct = total > 0 ? (count / total) * 100 : 0;
          const colors = TYPE_COLORS[type];
          return (
            <Tooltip key={type} content={`${TYPE_LABELS[type] ?? type}: ${count}`} position="bottom">
              <div
                className={`h-full ${colors?.bar ?? "bg-slate-400"}`}
                style={{ width: `${pct}%` }}
              />
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}
