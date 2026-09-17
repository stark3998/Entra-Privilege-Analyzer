import clsx from "clsx";
import type { RestoreConflict } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { RestoreConflictStatusBadge } from "@/components/governance/GovernanceBadges";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface RestoreConflictListProps {
  items: RestoreConflict[];
  selectedId: string | null;
  onSelect: (conflictId: string) => void;
  isLoading?: boolean;
}

export function RestoreConflictList({
  items,
  selectedId,
  onSelect,
  isLoading,
}: RestoreConflictListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="card animate-pulse p-4">
            <div className="h-4 w-1/3 rounded bg-slate-100 dark:bg-slate-800" />
            <div className="mt-3 h-6 w-full rounded bg-slate-100 dark:bg-slate-800" />
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="No restore conflicts"
        description="Restore conflicts will appear here when snapshots and current state drift require manual review."
      />
    );
  }

  return (
    <div className="space-y-3">
      {items.map((item) => {
        const isSelected = item.id === selectedId;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={clsx(
              "card w-full p-4 text-left transition-all",
              isSelected
                ? "border-brand-300 ring-2 ring-brand-100 dark:border-brand-700 dark:ring-brand-900/40"
                : "hover:border-slate-300 dark:hover:border-slate-600",
            )}
          >
            <div className="flex flex-wrap items-center gap-2">
              <RestoreConflictStatusBadge status={item.status} />
              <SeverityBadge severity={item.severity} />
            </div>
            <h3 className="mt-3 text-sm font-semibold text-slate-900 dark:text-white">
              {item.title}
            </h3>
            <p className="mt-1 line-clamp-2 text-sm text-slate-600 dark:text-slate-400">
              {item.summary}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span>{item.source_connector}</span>
              <span>•</span>
              <span>{item.resource_scope}</span>
              <span>•</span>
              <span>{formatRelativeTime(item.detected_at)}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
