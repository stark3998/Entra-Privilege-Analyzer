import type { ScopedCopilotRun } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { CopilotRunStatusBadge } from "@/components/governance/GovernanceBadges";
import { formatDateTime } from "@/utils/governanceFormatting";

export function ScopedCopilotRunList({
  runs,
  isLoading,
}: {
  runs: ScopedCopilotRun[];
  isLoading?: boolean;
}) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="card animate-pulse p-4">
            <div className="h-4 w-1/4 rounded bg-slate-100 dark:bg-slate-800" />
            <div className="mt-3 h-10 rounded bg-slate-100 dark:bg-slate-800" />
          </div>
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <EmptyState
        title="No scoped copilot runs"
        description="Launch a scoped copilot prompt to see recent investigations, summaries, and citations."
      />
    );
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <div key={run.id} className="card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <CopilotRunStatusBadge status={run.status} />
              <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {run.scope_name}
              </span>
              {run.persona_id && (
                <span className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
                  Persona: {run.persona_id}
                </span>
              )}
            </div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Started {formatDateTime(run.created_at)}
            </p>
          </div>

          <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
            {run.prompt}
          </p>

          {run.output_summary && (
            <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">
              {run.output_summary}
            </p>
          )}

          {run.output_markdown && (
            <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-950/95 px-3 py-3 text-xs text-slate-100">
              <code>{run.output_markdown}</code>
            </pre>
          )}

          {run.error_message && (
            <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
              {run.error_message}
            </p>
          )}

          {run.citations.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {run.citations.map((citation) => (
                <span
                  key={`${citation.target_type}-${citation.target_id}`}
                  className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                >
                  {citation.label}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
