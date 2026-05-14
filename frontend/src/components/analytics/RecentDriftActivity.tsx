import { Link } from "react-router-dom";
import clsx from "clsx";
import type { DriftAlert } from "@/api/types";

interface RecentDriftActivityProps {
  alerts: DriftAlert[];
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  low: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const now = Date.now();
  const diff = now - d.getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function RecentDriftActivity({ alerts }: RecentDriftActivityProps) {
  if (alerts.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
        No recent drift alerts
      </p>
    );
  }

  return (
    <div className="space-y-1">
      {alerts.map((alert) => (
        <Link
          key={alert.id}
          to={`../drift/${alert.id}`}
          className="group flex items-start gap-3 rounded-xl px-3 py-2.5 transition-all hover:bg-slate-50 dark:hover:bg-slate-800/60"
        >
          <div className="mt-0.5 flex h-2 w-2 flex-shrink-0 items-center justify-center">
            <span
              className={clsx(
                "block h-2 w-2 rounded-full",
                alert.severity === "critical" || alert.severity === "high"
                  ? "bg-red-500"
                  : alert.severity === "medium"
                    ? "bg-amber-500"
                    : "bg-slate-400",
              )}
            />
          </div>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-900 group-hover:text-brand-600 dark:text-white dark:group-hover:text-brand-400">
              {alert.action}
            </p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              {alert.identity_display_name}
            </p>
          </div>

          <div className="flex flex-shrink-0 items-center gap-2">
            <span
              className={clsx(
                "rounded px-1.5 py-0.5 text-[10px] font-medium",
                SEVERITY_COLORS[alert.severity] ?? SEVERITY_COLORS.low,
              )}
            >
              {alert.severity}
            </span>
            <span className="text-[10px] text-slate-400 dark:text-slate-500">
              {formatRelative(alert.detected_at)}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
