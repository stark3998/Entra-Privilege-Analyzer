// frontend/src/components/identities/ActionTimeline.tsx
import { useState } from "react";
import clsx from "clsx";
import { useActions } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface ActionTimelineProps {
  identityId: string;
}

const PAGE_SIZE = 20;

/**
 * Vertical timeline of action events for a single identity.
 * Supports pagination, loading, and empty states.
 */
export function ActionTimeline({ identityId }: ActionTimelineProps) {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, error } = useActions(identityId, {
    page,
    size: PAGE_SIZE,
  });

  if (isLoading) return <LoadingSpinner message="Loading actions..." />;

  if (isError) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
        Failed to load actions: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  const events = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (events.length === 0) {
    return (
      <EmptyState
        title="No actions recorded"
        description="Action events will appear here once log data is ingested."
        icon={
          <svg
            className="h-10 w-10"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Timeline */}
      <div className="relative ml-3 border-l-2 border-slate-200 pl-6 dark:border-slate-700">
        {events.map((event) => {
          const isSuccess =
            event.result.toLowerCase() === "success" ||
            event.result.toLowerCase() === "succeeded";

          return (
            <div key={event.id} className="relative mb-6 last:mb-0">
              {/* Dot on the timeline line */}
              <div
                className={clsx(
                  "absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-white dark:border-slate-900",
                  isSuccess ? "bg-emerald-500" : "bg-red-500",
                )}
              />

              <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800/60">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900 dark:text-white">
                      {event.action}
                    </p>
                    {event.resource && (
                      <p className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
                        {event.resource}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {/* Result badge */}
                    <span
                      className={clsx(
                        "inline-flex rounded px-1.5 py-0.5 text-xs font-medium",
                        isSuccess
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400"
                          : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
                      )}
                    >
                      {event.result}
                    </span>

                    {/* Source badge */}
                    <span className="inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                      {event.source}
                    </span>
                  </div>
                </div>

                <p className="mt-1.5 text-xs text-slate-400 dark:text-slate-500">
                  {formatRelativeTime(event.timestamp)}
                  {event.ip_address && (
                    <span className="ml-2">
                      IP: {event.ip_address}
                    </span>
                  )}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Page {page} of {totalPages} ({total} events)
          </p>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className={clsx(
                "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                page <= 1
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
              )}
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className={clsx(
                "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                page >= totalPages
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
              )}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
