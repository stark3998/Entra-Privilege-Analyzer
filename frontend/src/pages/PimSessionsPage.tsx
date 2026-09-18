import { useState } from "react";
import { usePimSessions, useActivePimSessions, useSyncPimSessions } from "@/api/hooks";
import { PimSessionTable } from "@/components/pim-sessions/PimSessionTable";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionItem, MotionStagger } from "@/components/common/motion";
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
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Privileged Identity Management</p>
          <h1 className="page-title mt-1">PIM Sessions</h1>
          <p className="page-subtitle">
            Track privileged role activations, session activity, and anomalies
          </p>
        </div>
        <div className="flex items-center gap-3">
          {activeCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <AnimatedNumber value={activeCount} /> active
            </span>
          )}
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="btn-primary"
          >
            {syncMutation.isPending ? "Syncing..." : "Sync Sessions"}
          </button>
        </div>
      </div>

      <MotionStagger className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MotionItem className="card p-4">
          <p className="eyebrow">Total Sessions</p>
          <AnimatedNumber value={total} className="mt-1 block text-2xl font-bold tabular-nums text-slate-900 dark:text-white" />
        </MotionItem>
        <MotionItem className="card p-4">
          <p className="eyebrow">Active Now</p>
          <AnimatedNumber value={activeCount} className="mt-1 block text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400" />
        </MotionItem>
        <MotionItem className="card p-4">
          <p className="eyebrow">Visible Results</p>
          <AnimatedNumber value={items.length} className="mt-1 block text-2xl font-bold tabular-nums text-brand-700 dark:text-brand-300" />
        </MotionItem>
      </MotionStagger>

      {/* Filters */}
      <div className="card flex flex-wrap items-center gap-3 p-4">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value as PimSessionStatus | ""); setPage(1); }}
          className="input-base"
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
          className="input-base"
        />

        <select
          value={anomalyFilter === undefined ? "" : anomalyFilter ? "yes" : "no"}
          onChange={(e) => {
            const v = e.target.value;
            setAnomalyFilter(v === "" ? undefined : v === "yes");
            setPage(1);
          }}
          className="input-base"
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
        <div className="card p-12 text-center">
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
            className="btn-secondary px-3 py-2 text-sm"
          >
            Previous
          </button>
          <span className="text-sm text-slate-600 dark:text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-secondary px-3 py-2 text-sm"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
