// frontend/src/pages/CustomRolesPage.tsx
import clsx from "clsx";
import { useCustomRoles } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import type { CustomRoleProfile } from "@/api/types";

export function CustomRolesPage() {
  const { data, isLoading } = useCustomRoles();

  const items: CustomRoleProfile[] = Array.isArray(data) ? data : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Custom Roles</h1>
        <p className="page-subtitle">
          Audit custom role definitions for wildcard permissions and escalation paths
        </p>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading custom roles..." />
      ) : items.length === 0 ? (
        <EmptyState
          title="No custom roles found"
          description="Run a scan to ingest custom role definitions from your target tenant."
          icon={
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
          <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Display Name</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Enabled</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Assignments</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Wildcard</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Escalation Paths</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {items.map((role) => (
                <tr key={role.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-slate-900 dark:text-white">{role.display_name}</div>
                    {role.description && (
                      <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400 line-clamp-1">{role.description}</div>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-center">
                    <span
                      className={clsx(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                        role.is_enabled
                          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                          : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                      )}
                    >
                      {role.is_enabled ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-center text-sm tabular-nums text-slate-700 dark:text-slate-300">
                    {role.assignment_count}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-center">
                    {role.has_wildcard ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700 dark:bg-red-900/30 dark:text-red-300">
                        <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                        Yes
                      </span>
                    ) : (
                      <span className="text-sm text-slate-400 dark:text-slate-500">No</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-center">
                    {role.has_escalation_paths ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-[11px] font-semibold text-orange-700 dark:bg-orange-900/30 dark:text-orange-300">
                        <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                        Yes
                      </span>
                    ) : (
                      <span className="text-sm text-slate-400 dark:text-slate-500">No</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
