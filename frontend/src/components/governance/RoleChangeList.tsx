import { Link } from "react-router-dom";
import type { RoleDiffSummary } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { MotionItem, MotionStagger } from "@/components/common/motion";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { RoleDiffStatusBadge } from "@/components/governance/GovernanceBadges";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface RoleChangeListProps {
  items: RoleDiffSummary[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  basePath: string;
  isLoading?: boolean;
}

function RoleDiffSkeleton() {
  return (
    <div className="card p-5">
      <div className="skeleton h-4 w-1/4" />
      <div className="skeleton mt-3 h-6 w-2/3" />
      <div className="skeleton mt-4 h-16" />
    </div>
  );
}

export function RoleChangeList({
  items,
  total,
  page,
  pageSize,
  onPageChange,
  basePath,
  isLoading,
}: RoleChangeListProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <RoleDiffSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="No risk assessments found"
        description="Proposed role changes will appear here with rollout and canary metadata."
      />
    );
  }

  return (
    <div className="space-y-4">
      <MotionStagger className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {items.map((item) => (
          <MotionItem key={item.id}>
          <Link to={`${basePath}/${item.id}`} className="card-interactive block p-5">
            <div className="flex flex-wrap items-center gap-2">
              <RoleDiffStatusBadge status={item.status} />
              <SeverityBadge severity={item.blast_radius} />
            </div>
            <div className="mt-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                {item.identity_display_name}
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {item.identity_type} • proposed by {item.proposed_by} {formatRelativeTime(item.proposed_at)}
              </p>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Reduction</p>
                <p className="mt-1 font-semibold text-emerald-600 dark:text-emerald-400">
                  {item.reduction_score}%
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Removed</p>
                <p className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {item.removed_permissions}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Added</p>
                <p className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {item.added_permissions}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Canary Events</p>
                <p className="mt-1 font-semibold text-slate-900 dark:text-white">
                  {item.canary_event_count}
                </p>
              </div>
            </div>
          </Link>
          </MotionItem>
        ))}
      </MotionStagger>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onPageChange(Math.max(1, page - 1))}
              disabled={page === 1}
              className="btn-secondary px-3 py-2 text-xs"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="btn-secondary px-3 py-2 text-xs"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
