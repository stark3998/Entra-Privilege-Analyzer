import { Link } from "react-router-dom";
import type { GovernanceWorkflow } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import {
  WorkflowStatusBadge,
  WorkflowTypeBadge,
} from "@/components/governance/GovernanceBadges";
import { formatRelativeTime } from "@/utils/formatRelativeTime";
import { formatDateTime } from "@/utils/governanceFormatting";

interface WorkflowInboxListProps {
  items: GovernanceWorkflow[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  basePath: string;
  isLoading?: boolean;
}

function WorkflowCardSkeleton() {
  return (
    <div className="card animate-pulse p-5">
      <div className="h-4 w-1/3 rounded bg-slate-100 dark:bg-slate-800" />
      <div className="mt-3 h-5 w-3/4 rounded bg-slate-100 dark:bg-slate-800" />
      <div className="mt-4 h-14 rounded bg-slate-100 dark:bg-slate-800" />
    </div>
  );
}

export function WorkflowInboxList({
  items,
  total,
  page,
  pageSize,
  onPageChange,
  basePath,
  isLoading,
}: WorkflowInboxListProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <WorkflowCardSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="No workflows in the inbox"
        description="Governance workflows will appear here after they are created by the backend."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {items.map((item) => (
          <Link
            key={item.id}
            to={`${basePath}/${item.id}`}
            className="card-interactive block p-5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <WorkflowStatusBadge status={item.status} />
              <WorkflowTypeBadge type={item.kind} />
            </div>

            <div className="mt-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="truncate text-lg font-semibold text-slate-900 dark:text-white">
                  {item.identity_id}
                </h2>
                <p className="mt-1 line-clamp-2 text-sm text-slate-600 dark:text-slate-400">
                  Workflow {item.id} created by {item.requested_by}
                </p>
              </div>
              <div className="text-right text-xs text-slate-500 dark:text-slate-400">
                <p>Created {formatRelativeTime(item.created_at)}</p>
                <p className="mt-1">Updated {formatRelativeTime(item.updated_at)}</p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Persona</p>
                <p className="mt-1 font-medium text-slate-900 dark:text-white">
                  {item.persona_id ?? "None"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Steps</p>
                <p className="mt-1 font-medium text-slate-900 dark:text-white">
                  {item.steps.length}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Approvals</p>
                <p className="mt-1 font-medium text-slate-900 dark:text-white">
                  {item.approvals.length}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Completed actions</p>
                <p className="mt-1 font-medium text-slate-900 dark:text-white">
                  {item.completed_action_ids.length}
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              {item.risk_assessment_id && (
                <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-800">
                  Risk: {item.risk_assessment_id}
                </span>
              )}
              {item.snapshot_id && (
                <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-800">
                  Snapshot: {item.snapshot_id}
                </span>
              )}
              <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-800">
                Next wake: {formatDateTime(item.next_wake_at)}
              </span>
              {item.error && (
                <span className="rounded-full bg-red-50 px-2.5 py-1 text-red-700 dark:bg-red-900/20 dark:text-red-300">
                  {item.error}
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}
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
