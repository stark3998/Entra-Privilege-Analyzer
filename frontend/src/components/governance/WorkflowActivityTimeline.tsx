import type { WorkflowActivity } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { formatDateTime, toTitleCase } from "@/utils/governanceFormatting";

export function WorkflowActivityTimeline({
  activities,
}: {
  activities: WorkflowActivity[];
}) {
  if (activities.length === 0) {
    return (
      <EmptyState
        title="No workflow activity yet"
        description="Approvals, escalations, and evidence updates will appear here as the workflow progresses."
      />
    );
  }

  return (
    <div className="space-y-4">
      {activities.map((activity, index) => (
        <div key={activity.id} className="flex gap-4">
          <div className="flex w-6 flex-col items-center">
            <span className="mt-1 h-2.5 w-2.5 rounded-full bg-brand-500" />
            {index < activities.length - 1 && (
              <span className="mt-1 h-full w-px bg-slate-200 dark:bg-slate-700" />
            )}
          </div>
          <div className="flex-1 rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-800/40">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  {toTitleCase(activity.action)}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {activity.actor}
                  {activity.actor_role ? ` • ${activity.actor_role}` : ""}
                </p>
              </div>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {formatDateTime(activity.created_at)}
              </p>
            </div>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
              {activity.message}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
