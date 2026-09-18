// frontend/src/components/identities/ActionTimeline.tsx
import { useState } from "react";
import clsx from "clsx";
import { useActions } from "@/api/hooks";
import { EmptyState } from "@/components/common/EmptyState";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionStagger, MotionItem } from "@/components/common/motion";
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

  if (isLoading) {
    return (
      <div className="card p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <div className="skeleton h-3 w-24" />
            <div className="skeleton mt-2 h-5 w-40" />
          </div>
          <div className="skeleton h-9 w-24" />
        </div>
        <div className="space-y-4">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="flex gap-4">
              <div className="skeleton h-3 w-3 rounded-full" />
              <div className="skeleton h-20 flex-1" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="card border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
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
    <div className="card p-5">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Event stream</p>
          <h3 className="section-title mt-1">Recent actions</h3>
        </div>
        <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          <AnimatedNumber value={total} />
          events
        </span>
      </div>

      {/* Timeline */}
      <MotionStagger className="relative ml-3 border-l border-slate-200 pl-6 dark:border-slate-800">
        {events.map((event) => {
          const isSuccess =
            event.result.toLowerCase() === "success" ||
            event.result.toLowerCase() === "succeeded";

          return (
            <MotionItem key={event.id} className="relative mb-6 last:mb-0">
              {/* Dot on the timeline line */}
              <div
                className={clsx(
                  "absolute -left-[31px] top-4 h-3 w-3 rounded-full border-2 border-white shadow-sm dark:border-slate-900",
                  isSuccess ? "bg-emerald-500" : "bg-red-500",
                )}
              />

              <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-xs transition-colors hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800/60">
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
                        "badge",
                        isSuccess
                          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                          : "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300",
                      )}
                    >
                      {event.result}
                    </span>

                    {/* Source badge */}
                    <span className="chip">
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
            </MotionItem>
          );
        })}
      </MotionStagger>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Page {page} of {totalPages} · {total} events
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="btn-secondary px-3 py-1.5 text-xs"
            >
              Prev
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="btn-secondary px-3 py-1.5 text-xs"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
