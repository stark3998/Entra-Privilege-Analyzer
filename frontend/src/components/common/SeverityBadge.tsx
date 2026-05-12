import clsx from "clsx";

type Severity = "low" | "medium" | "high" | "critical";

interface SeverityBadgeProps {
  severity: Severity;
  size?: "sm" | "md";
}

const SEVERITY_COLORS: Record<Severity, { bg: string; dot: string }> = {
  low: { bg: "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300", dot: "bg-slate-400" },
  medium: { bg: "bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300", dot: "bg-amber-500" },
  high: { bg: "bg-orange-50 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300", dot: "bg-orange-500" },
  critical: { bg: "bg-red-50 text-red-700 dark:bg-red-900/40 dark:text-red-300", dot: "bg-red-500" },
};

const SIZE_CLASSES: Record<"sm" | "md", string> = {
  sm: "px-2 py-0.5 text-[11px]",
  md: "px-2.5 py-1 text-xs",
};

export function SeverityBadge({ severity, size = "sm" }: SeverityBadgeProps) {
  const colors = SEVERITY_COLORS[severity];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full font-semibold capitalize",
        colors.bg,
        SIZE_CLASSES[size],
      )}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", colors.dot)} />
      {severity}
    </span>
  );
}
