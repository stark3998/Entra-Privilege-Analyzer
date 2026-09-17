import type { CanaryTimelineEvent } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { RoleDiffStatusBadge } from "@/components/governance/GovernanceBadges";
import { formatDateTime, toTitleCase } from "@/utils/governanceFormatting";

export function CanaryTimeline({
  events,
}: {
  events: CanaryTimelineEvent[];
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title="No canary activity yet"
        description="Canary validation events will appear here when a role change moves into guarded rollout."
      />
    );
  }

  return (
    <div className="space-y-4">
      {events.map((event, index) => (
        <div key={event.id} className="flex gap-4">
          <div className="flex w-6 flex-col items-center">
            <span className="mt-1 h-2.5 w-2.5 rounded-full bg-blue-500" />
            {index < events.length - 1 && (
              <span className="mt-1 h-full w-px bg-slate-200 dark:bg-slate-700" />
            )}
          </div>
          <div className="flex-1 rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-800/40">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {toTitleCase(event.stage)}
                </p>
                <RoleDiffStatusBadge status={event.status === "passed" ? "completed" : event.status === "running" ? "canary_running" : event.status === "failed" ? "canary_failed" : event.status === "rolled_back" ? "rolled_back" : "proposed"} />
              </div>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {formatDateTime(event.timestamp)}
              </p>
            </div>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">{event.summary}</p>
            {(event.metric_name || event.threshold) && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                {event.metric_name && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-800">
                    Metric: {event.metric_name}
                    {typeof event.metric_value === "number" ? ` = ${event.metric_value}` : ""}
                  </span>
                )}
                {event.threshold && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-slate-800">
                    Threshold: {event.threshold}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
