// frontend/src/components/best-practices/ComplianceGauge.tsx
import { useEffect, useState } from "react";
import clsx from "clsx";

interface ComplianceGaugeProps {
  /** Compliance score from 0 to 100. */
  score: number;
  /** Size of the SVG in pixels. Defaults to 120. */
  size?: number;
}

/** Return color classes based on compliance score thresholds. */
function scoreColors(score: number): { stroke: string; text: string } {
  if (score > 80)
    return {
      stroke: "text-emerald-500",
      text: "text-emerald-700 dark:text-emerald-400",
    };
  if (score > 60)
    return {
      stroke: "text-amber-500",
      text: "text-amber-700 dark:text-amber-400",
    };
  return {
    stroke: "text-red-500",
    text: "text-red-700 dark:text-red-400",
  };
}

/**
 * Circular compliance score gauge with animated fill on mount.
 * Color: >80 = green, >60 = amber, else red.
 *
 * Usage:
 * ```tsx
 * <ComplianceGauge score={75} size={140} />
 * ```
 */
export function ComplianceGauge({ score, size = 120 }: ComplianceGaugeProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedScore / 100) * circumference;
  const colors = scoreColors(score);

  // Animate score from 0 to target on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedScore(score);
    }, 50);
    return () => clearTimeout(timer);
  }, [score]);

  return (
    <div className="flex flex-col items-center">
      <div className="relative">
        <svg width={size} height={size} className="-rotate-90">
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-slate-200 dark:text-slate-700"
          />
          {/* Progress arc */}
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
        {/* Score number in center */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={clsx(
              "text-3xl font-bold tabular-nums",
              colors.text,
            )}
          >
            {Math.round(animatedScore)}
          </span>
        </div>
      </div>
      <p className="mt-2 text-sm font-medium text-slate-500 dark:text-slate-400">
        Compliance Score
      </p>
    </div>
  );
}
