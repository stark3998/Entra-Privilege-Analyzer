import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Tooltip } from "@/components/common/Tooltip";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { useProjectContext } from "@/store/projectContext";

interface RiskScoreCardProps {
  score: number;
  highRiskCount: number;
}

function riskColors(score: number) {
  if (score > 70)
    return {
      ring: "#ef4444",
      text: "text-red-600 dark:text-red-400",
      label: "High Risk",
      chip: "bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400",
      glow: "from-red-50/80 to-transparent dark:from-red-950/20",
    };
  if (score > 40)
    return {
      ring: "#f59e0b",
      text: "text-amber-600 dark:text-amber-400",
      label: "Medium Risk",
      chip: "bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400",
      glow: "from-amber-50/80 to-transparent dark:from-amber-950/20",
    };
  return {
    ring: "#22c55e",
    text: "text-emerald-600 dark:text-emerald-400",
    label: "Low Risk",
    chip: "bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400",
    glow: "from-emerald-50/80 to-transparent dark:from-emerald-950/20",
  };
}

export function RiskScoreCard({ score, highRiskCount }: RiskScoreCardProps) {
  const navigate = useNavigate();
  const { projectId } = useProjectContext();
  const size = 132;
  const strokeWidth = 11;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const colors = riskColors(score);

  return (
    <div
      onClick={() => navigate(`/projects/${projectId}/identities`)}
      className="card-interactive group relative h-full overflow-hidden p-6"
    >
      <div
        className={clsx(
          "pointer-events-none absolute inset-0 bg-gradient-to-br opacity-70",
          colors.glow,
        )}
      />
      <div className="relative flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="eyebrow">Tenant Risk Score</p>
            <Tooltip content="Composite score based on identity risk factors, drift alerts, and compliance">
              <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </Tooltip>
          </div>
          <span className={clsx("mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", colors.chip)}>
            <span className="h-1.5 w-1.5 rounded-full bg-current" />
            {colors.label}
          </span>
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
            <span className="font-bold text-slate-800 dark:text-slate-100">
              <AnimatedNumber value={highRiskCount} />
            </span>{" "}
            high-risk {highRiskCount === 1 ? "identity" : "identities"}
          </p>
          <div className="mt-3 flex items-center gap-1 text-xs font-semibold text-brand-600 opacity-0 transition-opacity group-hover:opacity-100 dark:text-brand-400">
            <span>Explore identities</span>
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>

        <div className="relative flex-shrink-0">
          <svg width={size} height={size} className="-rotate-90">
            <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={strokeWidth} className="stroke-slate-100 dark:stroke-slate-800" />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={colors.ring}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.16,1,0.3,1)" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <AnimatedNumber value={score} decimals={0} className={clsx("text-4xl font-bold tabular-nums", colors.text)} />
            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">/ 100</span>
          </div>
        </div>
      </div>
    </div>
  );
}
