import { useState } from "react";
import { usePimSessions, useActivePimSessions, useSyncPimSessions } from "@/api/hooks";
import { PimSessionTable } from "@/components/pim-sessions/PimSessionTable";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { PimSessionStatus } from "@/api/types";

const STATUS_OPTIONS: { label: string; value: PimSessionStatus | "" }[] = [
  { label: "All Statuses", value: "" },
  { label: "Active", value: "active" },
  { label: "Expired", value: "expired" },
  { label: "Deactivated", value: "deactivated" },
];

const PAGE_SIZE = 20;

export function PimSessionsPage() {
  const [statusFilter, setStatusFilter] = useState<PimSessionStatus | "">("");
  const [roleFilter, setRoleFilter] = useState("");
  const [anomalyFilter, setAnomalyFilter] = useState<boolean | undefined>(undefined);
  const [page, setPage] = useState(1);

  const { data, isLoading } = usePimSessions({
    status: statusFilter || undefined,
    roleName: roleFilter || undefined,
    hasAnomalies: anomalyFilter,
    page,
    size: PAGE_SIZE,
  });

  const { data: activeData } = useActivePimSessions();
  const syncMutation = useSyncPimSessions();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeCount = activeData?.total ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            PIM Sessions
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Track privileged role activations, session activity, and anomalies
          </p>
        </div>
        <div className="flex items-center gap-3">
          {activeCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-sm font-medium text-green-700 dark:bg-green-900/20 dark:text-green-300">
              <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              {activeCount} active
            </span>
          )}
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {syncMutation.isPending ? "Syncing..." : "Sync Sessions"}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value as PimSessionStatus | ""); setPage(1); }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Filter by role name..."
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white"
        />

        <select
          value={anomalyFilter === undefined ? "" : anomalyFilter ? "yes" : "no"}
          onChange={(e) => {
            const v = e.target.value;
            setAnomalyFilter(v === "" ? undefined : v === "yes");
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-white"
        >
          <option value="">All Sessions</option>
          <option value="yes">With Anomalies</option>
          <option value="no">No Anomalies</option>
        </select>

        <span className="ml-auto text-sm text-slate-500 dark:text-slate-400">
          {total} session{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      {isLoading ? (
        <LoadingSpinner />
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-12 text-center dark:border-slate-700 dark:bg-slate-800">
          <p className="text-slate-500 dark:text-slate-400">
            No PIM sessions found. Trigger a scan or sync to discover sessions.
          </p>
        </div>
      ) : (
        <PimSessionTable sessions={items} />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-slate-600 dark:text-white"
          >
            Previous
          </button>
          <span className="text-sm text-slate-600 dark:text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-slate-600 dark:text-white"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
