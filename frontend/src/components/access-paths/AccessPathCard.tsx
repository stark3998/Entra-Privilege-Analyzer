import type { AccessPath } from "@/api/types";
import { SeverityBadge } from "@/components/common/SeverityBadge";

const EXPLOIT_LABELS: Record<string, { text: string; color: string }> = {
  direct: { text: "Direct Access", color: "text-red-600 dark:text-red-400" },
  requires_credential_addition: {
    text: "Requires Credential Addition",
    color: "text-amber-600 dark:text-amber-400",
  },
  requires_group_membership_change: {
    text: "Requires Group Membership Change",
    color: "text-amber-600 dark:text-amber-400",
  },
};

interface AccessPathCardProps {
  path: AccessPath;
  selected?: boolean;
  onClick?: () => void;
}

export function AccessPathCard({ path, selected, onClick }: AccessPathCardProps) {
  const exploit = EXPLOIT_LABELS[path.exploitability] ?? {
    text: path.exploitability,
    color: "text-slate-500",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-lg border p-3 text-left transition-colors ${
        selected
          ? "border-indigo-400 bg-indigo-50 dark:border-indigo-600 dark:bg-indigo-900/20"
          : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <SeverityBadge severity={path.risk_level as "critical" | "high" | "medium"} />
        <span className={`text-[10px] font-medium ${exploit.color}`}>{exploit.text}</span>
      </div>
      <p className="mt-1.5 text-xs text-slate-700 dark:text-slate-300 line-clamp-2">
        {path.description}
      </p>
      <p className="mt-1 text-[10px] font-semibold text-slate-900 dark:text-white">
        Target: {path.target_privilege}
      </p>
    </button>
  );
}
