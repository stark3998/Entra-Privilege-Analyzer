// frontend/src/components/dashboard/RiskScoreCard.tsx
import { useEffect, useState } from "react";
import clsx from "clsx";

interface RiskScoreCardProps {
  /** Risk score from 0 to 100. */
  score: number;
  /** Number of high-risk identities. */
  highRiskCount: number;
}

/** Return color classes based on risk score thresholds (inverted from compliance). */
function riskColors(score: number): { stroke: string; text: string } {
  if (score > 70)
    return {
      stroke: "text-red-500",
      text: "text-red-700 dark:text-red-400",
    };
  if (score > 40)
    return {
      stroke: "text-amber-500",
      text: "text-amber-700 dark:text-amber-400",
    };
  return {
    stroke: "text-emerald-500",
    text: "text-emerald-700 dark:text-emerald-400",
  };
}

/**
 * Large risk score card with circular SVG gauge.
 * Risk coloring: >70 red, >40 amber, else green.
 *
 * Usage:
 * ```tsx
 * <RiskScoreCard score={65} highRiskCount={12} />
 * ```
 */
export function RiskScoreCard({ score, highRiskCount }: RiskScoreCardProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const size = 160;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;
  const colors = riskColors(score);

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedScore(score);
    }, 50);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex flex-col items-center">
        <div className="relative">
          <svg width={size} height={size} className="-rotate-90">
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="currentColor"
              strokeWidth={strokeWidth}
              className="text-slate-200 dark:text-slate-700"
            />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="currentColor"
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className={clsx(colors.stroke, "transition-all duration-700 ease-out")}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span
              className={clsx(
                "text-4xl font-bold tabular-nums",
                colors.text,
              )}
            >
              {Math.round(animatedScore)}
            </span>
          </div>
        </div>
        <p className="mt-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
          Tenant Risk Score
        </p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {highRiskCount} high-risk {highRiskCount === 1 ? "identity" : "identities"}
        </p>
      </div>
    </div>
  );
}
