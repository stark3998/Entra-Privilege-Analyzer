// frontend/src/pages/ConditionalAccessPage.tsx
import clsx from "clsx";
import { useCAPolicies } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import type { ConditionalAccessPolicy } from "@/api/types";

const STATE_STYLE: Record<string, { bg: string; text: string }> = {
  enabled: { bg: "bg-emerald-50 dark:bg-emerald-900/30", text: "text-emerald-700 dark:text-emerald-300" },
  disabled: { bg: "bg-slate-100 dark:bg-slate-700", text: "text-slate-600 dark:text-slate-300" },
  enabledForReportingButNotEnforced: { bg: "bg-amber-50 dark:bg-amber-900/30", text: "text-amber-700 dark:text-amber-300" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function stateLabel(state: string): string {
  if (state === "enabledForReportingButNotEnforced") return "Report Only";
  return state.charAt(0).toUpperCase() + state.slice(1);
}

export function ConditionalAccessPage() {
  const { data, isLoading } = useCAPolicies();

  const items: ConditionalAccessPolicy[] = Array.isArray(data) ? data : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Conditional Access Policies</h1>
        <p className="page-subtitle">
          Review conditional access policies, their states, and last modification dates
        </p>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading conditional access policies..." />
      ) : items.length === 0 ? (
        <EmptyState
          title="No conditional access policies found"
          description="Run a scan to ingest conditional access policies from your target tenant."
          icon={
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
          <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Policy Name</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">State</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Created</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Modified</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {items.map((policy) => {
                const style = STATE_STYLE[policy.state] ?? STATE_STYLE.disabled;
                return (
                  <tr key={policy.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-slate-900 dark:text-white">
                      {policy.display_name}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center">
                      <span
                        className={clsx(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
                          style.bg,
                          style.text,
                        )}
                      >
                        {stateLabel(policy.state)}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                      {formatDate(policy.created_date_time)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-slate-500 dark:text-slate-400">
                      {formatDate(policy.modified_date_time)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
