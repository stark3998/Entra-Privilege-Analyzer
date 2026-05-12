import { useNavigate } from "react-router-dom";
import { Tooltip } from "@/components/common/Tooltip";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  low: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
};

interface DriftSummaryCardProps {
  total: number;
  bySeverity: Record<string, number>;
}

export function DriftSummaryCard({ total, bySeverity }: DriftSummaryCardProps) {
  const navigate = useNavigate();
  const severities = ["critical", "high", "medium", "low"] as const;

  return (
    <div
      onClick={() => navigate("/drift")}
      className="card-interactive p-6"
    >
      <div className="flex items-center gap-2">
        <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Open Drift Alerts
        </p>
        <Tooltip content="Permission anomalies detected via first-seen and z-score analysis">
          <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </Tooltip>
      </div>
      <p className="mt-1 text-3xl font-bold tabular-nums text-slate-900 dark:text-white">
        {total.toLocaleString()}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {severities.map((sev) => {
          const count = bySeverity[sev] ?? 0;
          return (
            <span
              key={sev}
              className={`badge capitalize ${SEVERITY_COLORS[sev] ?? ""}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
              {sev}: {count}
            </span>
          );
        })}
      </div>

      <div className="mt-4 flex items-center gap-1 text-sm font-medium text-brand-600 dark:text-brand-400">
        <span>View all alerts</span>
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}
