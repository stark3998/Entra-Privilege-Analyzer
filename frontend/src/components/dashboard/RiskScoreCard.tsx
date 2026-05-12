import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Tooltip } from "@/components/common/Tooltip";

interface RiskScoreCardProps {
  score: number;
  highRiskCount: number;
}

function riskColors(score: number): { stroke: string; text: string; label: string; bg: string } {
  if (score > 70)
    return { stroke: "text-red-500", text: "text-red-600 dark:text-red-400", label: "High Risk", bg: "from-red-50 to-white dark:from-red-950/20 dark:to-slate-900" };
  if (score > 40)
    return { stroke: "text-amber-500", text: "text-amber-600 dark:text-amber-400", label: "Medium Risk", bg: "from-amber-50 to-white dark:from-amber-950/20 dark:to-slate-900" };
  return { stroke: "text-emerald-500", text: "text-emerald-600 dark:text-emerald-400", label: "Low Risk", bg: "from-emerald-50 to-white dark:from-emerald-950/20 dark:to-slate-900" };
}

export function RiskScoreCard({ score, highRiskCount }: RiskScoreCardProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const navigate = useNavigate();
  const size = 140;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;
  const colors = riskColors(score);

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(score), 50);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div
      onClick={() => navigate("/identities")}
      className={clsx(
        "card-interactive cursor-pointer bg-gradient-to-br p-6",
        colors.bg,
      )}
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Tenant Risk Score
            </p>
            <Tooltip content="Composite score based on identity risk factors, drift alerts, and compliance">
              <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </Tooltip>
          </div>
          <p className={clsx("mt-1 text-xs font-medium", colors.text)}>
            {colors.label}
          </p>
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            <span className="font-semibold text-slate-700 dark:text-slate-300">{highRiskCount}</span>{" "}
            high-risk {highRiskCount === 1 ? "identity" : "identities"}
          </p>
        </div>

        <div className="relative flex-shrink-0">
          <svg width={size} height={size} className="-rotate-90">
            <circle
              cx={size / 2} cy={size / 2} r={radius}
              fill="none" stroke="currentColor" strokeWidth={strokeWidth}
              className="text-slate-100 dark:text-slate-800"
            />
            <circle
              cx={size / 2} cy={size / 2} r={radius}
              fill="none" stroke="currentColor" strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className={clsx(colors.stroke, "transition-all duration-700 ease-out")}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={clsx("text-3xl font-bold tabular-nums", colors.text)}>
              {Math.round(animatedScore)}
            </span>
            <span className="text-[10px] font-medium text-slate-400">/ 100</span>
          </div>
        </div>
      </div>
    </div>
  );
}
