import { useNavigate } from "react-router-dom";
import { Tooltip } from "@/components/common/Tooltip";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { useProjectContext } from "@/store/projectContext";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300",
  high: "bg-orange-50 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300",
  medium: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
  low: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

interface DriftSummaryCardProps {
  total: number;
  bySeverity: Record<string, number>;
}

export function DriftSummaryCard({ total, bySeverity }: DriftSummaryCardProps) {
  const navigate = useNavigate();
  const { projectId } = useProjectContext();
  const severities = ["critical", "high", "medium", "low"] as const;

  return (
    <div
      onClick={() => navigate(`/projects/${projectId}/drift`)}
      className="card-interactive group h-full p-6"
    >
      <div className="flex items-center gap-2">
        <p className="eyebrow">Open Drift Alerts</p>
        <Tooltip content="Permission anomalies detected via first-seen and z-score analysis">
          <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </Tooltip>
      </div>
      <AnimatedNumber
        value={total}
        className="mt-2 block text-4xl font-bold tabular-nums text-slate-900 dark:text-white"
      />

      <div className="mt-5 flex flex-wrap gap-2">
        {severities.map((sev) => {
          const count = bySeverity[sev] ?? 0;
          return (
            <span
              key={sev}
              className={`badge capitalize ${SEVERITY_COLORS[sev] ?? ""}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
              {sev}: {count}
            </span>
          );
        })}
      </div>

      <div className="mt-5 flex items-center gap-1 text-xs font-semibold text-brand-600 transition-transform group-hover:translate-x-0.5 dark:text-brand-400">
        <span>View all alerts</span>
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </div>
    </div>
  );
}
