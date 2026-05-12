import { useEffect, useState } from "react";
import clsx from "clsx";

interface ComplianceGaugeProps {
  score: number;
  size?: number;
}

function scoreColors(score: number): { stroke: string; text: string; label: string } {
  if (score > 80)
    return { stroke: "text-emerald-500", text: "text-emerald-600 dark:text-emerald-400", label: "Good" };
  if (score > 60)
    return { stroke: "text-amber-500", text: "text-amber-600 dark:text-amber-400", label: "Fair" };
  return { stroke: "text-red-500", text: "text-red-600 dark:text-red-400", label: "Needs Work" };
}

export function ComplianceGauge({ score, size = 120 }: ComplianceGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;
  const colors = scoreColors(score);

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(score), 50);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div className="flex flex-col items-center">
      <div className="relative">
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
          <span className={clsx("text-2xl font-bold tabular-nums", colors.text)}>
            {Math.round(animatedScore)}
          </span>
          <span className="text-[10px] font-medium text-slate-400">/ 100</span>
        </div>
      </div>
      <p className={clsx("mt-2 text-xs font-semibold", colors.text)}>
        {colors.label}
      </p>
      <p className="text-[10px] font-medium text-slate-400 dark:text-slate-500">
        Compliance Score
      </p>
    </div>
  );
}
