// frontend/src/pages/AppRegistrationsPage.tsx
import { useState } from "react";
import clsx from "clsx";
import { useAppRegistrations } from "@/api/hooks";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import type { AppRegistrationProfile } from "@/api/types";

const PAGE_SIZE = 50;

export function AppRegistrationsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useAppRegistrations(page, PAGE_SIZE);

  const items: AppRegistrationProfile[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">App Registrations</h1>
        <p className="page-subtitle">
          Review application registrations, credential status, and high-risk permission grants
        </p>
      </div>

      {isLoading ? (
        <LoadingSpinner message="Loading app registrations..." />
      ) : items.length === 0 ? (
        <EmptyState
          title="No app registrations found"
          description="Run a scan to ingest app registration data from your target tenant."
          icon={
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
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
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">App ID</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Multi-Tenant</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Credentials</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Expired</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">High-Risk Perms</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {items.map((app) => {
                  const allCreds = [...app.password_credentials, ...app.key_credentials];
                  const expiredCount = allCreds.filter((c) => c.is_expired).length;
                  return (
                    <tr key={app.id} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-slate-900 dark:text-white">
                        {app.display_name}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">
                        {app.app_id}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center">
                        <span
                          className={clsx(
                            "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold",
                            app.is_multi_tenant
                              ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
                              : "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                          )}
                        >
                          {app.is_multi_tenant ? "Yes" : "No"}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center text-sm tabular-nums text-slate-700 dark:text-slate-300">
                        {allCreds.length}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center">
                        {expiredCount > 0 ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-700 dark:bg-red-900/30 dark:text-red-300">
                            <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                            {expiredCount}
                          </span>
                        ) : (
                          <span className="text-sm text-slate-400 dark:text-slate-500">0</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center">
                        {app.high_risk_permissions.length > 0 ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-[11px] font-semibold text-orange-700 dark:bg-orange-900/30 dark:text-orange-300">
                            {app.high_risk_permissions.length}
                          </span>
                        ) : (
                          <span className="text-sm text-slate-400 dark:text-slate-500">0</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
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
