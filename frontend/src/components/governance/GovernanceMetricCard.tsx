import clsx from "clsx";

type Tone = "slate" | "brand" | "emerald" | "amber" | "orange" | "red" | "purple";

const TONE_CLASSES: Record<Tone, string> = {
  slate: "text-slate-900 dark:text-white",
  brand: "text-brand-700 dark:text-brand-300",
  emerald: "text-emerald-600 dark:text-emerald-400",
  amber: "text-amber-600 dark:text-amber-400",
  orange: "text-orange-600 dark:text-orange-400",
  red: "text-red-600 dark:text-red-400",
  purple: "text-purple-600 dark:text-purple-400",
};

interface GovernanceMetricCardProps {
  label: string;
  value: string | number;
  caption?: string;
  tone?: Tone;
}

export function GovernanceMetricCard({
  label,
  value,
  caption,
  tone = "slate",
}: GovernanceMetricCardProps) {
  return (
    <div className="card px-4 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className={clsx("mt-1 text-2xl font-bold tabular-nums", TONE_CLASSES[tone])}>
        {value}
      </p>
      {caption && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{caption}</p>
      )}
    </div>
  );
}
