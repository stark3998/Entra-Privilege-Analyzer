// frontend/src/pages/GroupsPage.tsx
import { useState } from "react";
import clsx from "clsx";
import { useGroups } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import type { GroupProfile } from "@/api/types";

const PAGE_SIZE = 50;

export function GroupsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useGroups(page, PAGE_SIZE);

  const items: GroupProfile[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Groups</h1>
        <p className="page-subtitle">
          Inspect group memberships, role assignments, dynamic rules, and ownership
        </p>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading groups..." />
      ) : items.length === 0 ? (
        <EmptyState
          title="No groups found"
          description="Run a scan to ingest group data from your target tenant."
          icon={
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/50">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Display Name</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Role-Assignable</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Dynamic</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Members</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Owners</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Roles</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((group) => (
                  <tr key={group.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-slate-900 dark:text-white">
                      {group.display_name}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center">
                      <span
                        className={clsx(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                          group.is_role_assignable
                            ? "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"
                            : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                        )}
                      >
                        {group.is_role_assignable ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center">
                      <span
                        className={clsx(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                          group.is_dynamic
                            ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                            : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                        )}
                      >
                        {group.is_dynamic ? "Yes" : "No"}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-sm tabular-nums text-slate-700 dark:text-slate-300">
                      {group.member_count}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-sm tabular-nums text-slate-700 dark:text-slate-300">
                      {group.owner_count}
                    </td>
                    <td className="px-4 py-3">
                      {group.roles_assigned.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {group.roles_assigned.map((role) => (
                            <span
                              key={role}
                              className="inline-flex rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 dark:bg-brand-900/30 dark:text-brand-300"
                            >
                              {role}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400 dark:text-slate-500">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
