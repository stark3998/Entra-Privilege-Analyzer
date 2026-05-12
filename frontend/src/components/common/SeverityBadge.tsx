// frontend/src/components/common/SeverityBadge.tsx
import clsx from "clsx";

type Severity = "low" | "medium" | "high" | "critical";

interface SeverityBadgeProps {
  severity: Severity;
  size?: "sm" | "md";
}

const SEVERITY_COLORS: Record<Severity, string> = {
  low: "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  critical: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
};

const SIZE_CLASSES: Record<"sm" | "md", string> = {
  sm: "px-1.5 py-0.5 text-xs",
  md: "px-2.5 py-1 text-xs",
};

/**
 * Reusable severity pill badge.
 * Colors: low=slate, medium=amber, high=orange, critical=red.
 */
export function SeverityBadge({ severity, size = "sm" }: SeverityBadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full font-medium capitalize",
        SEVERITY_COLORS[severity],
        SIZE_CLASSES[size],
      )}
    >
      {severity}
    </span>
  );
}
