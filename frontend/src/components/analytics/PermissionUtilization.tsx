import { useEffect, useState } from "react";
import clsx from "clsx";

interface PermissionUtilizationProps {
  used: number;
  unused: number;
}

export function PermissionUtilization({
  used,
  unused,
}: PermissionUtilizationProps) {
  const total = used + unused;
  const pct = total > 0 ? Math.round((used / total) * 100) : 0;
  const [animatedPct, setAnimatedPct] = useState(0);

  const size = 120;
  const strokeWidth = 10;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedPct / 100) * circumference;

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedPct(pct), 50);
    return () => clearTimeout(timer);
  }, [pct]);

  const color =
    pct > 70
      ? { stroke: "text-emerald-500", text: "text-emerald-600 dark:text-emerald-400" }
      : pct > 40
        ? { stroke: "text-amber-500", text: "text-amber-600 dark:text-amber-400" }
        : { stroke: "text-red-500", text: "text-red-600 dark:text-red-400" };

  return (
    <div className="flex items-center gap-6">
      <div className="relative flex-shrink-0">
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-slate-100 dark:text-slate-800"
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
            className={clsx(color.stroke, "transition-all duration-700 ease-out")}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={clsx("text-xl font-bold tabular-nums", color.text)}>
            {animatedPct}%
          </span>
          <span className="text-[10px] font-medium text-slate-400">used</span>
        </div>
      </div>
      <div className="space-y-2 text-xs">
        <div>
          <p className="font-semibold text-emerald-600 dark:text-emerald-400">
            {used.toLocaleString()} used
          </p>
          <p className="text-slate-400">Permissions actively exercised</p>
        </div>
        <div>
          <p className="font-semibold text-red-500 dark:text-red-400">
            {unused.toLocaleString()} unused
          </p>
          <p className="text-slate-400">Granted but never observed</p>
        </div>
      </div>
    </div>
  );
}
