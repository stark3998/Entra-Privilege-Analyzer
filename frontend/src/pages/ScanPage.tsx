import { useState } from "react";
import clsx from "clsx";
import {
  useScanHistory,
  useLatestScan,
  useTriggerScan,
} from "@/api/projectHooks";
import { useProjectContext } from "@/store/projectContext";
import type { ScanRecord, ScanPhase } from "@/api/types";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed:
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400",
    running:
      "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400",
    queued:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
    failed: "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400",
  };
  return (
    <span className={`badge ${styles[status] ?? styles.queued}`}>
      {status}
    </span>
  );
}

function PhaseRow({ phase }: { phase: ScanPhase }) {
  const label = phase.name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/50 px-4 py-2.5 dark:border-slate-800 dark:bg-slate-800/30">
      <div className="flex items-center gap-3">
        {phase.status === "completed" ? (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/30">
            <svg className="h-3 w-3 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
        ) : phase.status === "running" ? (
          <svg className="h-5 w-5 animate-spin text-blue-500" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        ) : phase.status === "failed" ? (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
            <svg className="h-3 w-3 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
        ) : (
          <div className="h-5 w-5 rounded-full border-2 border-slate-200 dark:border-slate-700" />
        )}
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
        </span>
      </div>
      <span className="text-xs tabular-nums text-slate-500 dark:text-slate-400">
        {phase.items_processed > 0
          ? `${phase.items_processed.toLocaleString()} items`
          : ""}
      </span>
    </div>
  );
}

function ScanHistoryRow({
  scan,
  expanded,
  onToggle,
}: {
  scan: ScanRecord;
  expanded: boolean;
  onToggle: () => void;
}) {
  const duration =
    scan.completed_at && scan.started_at
      ? Math.round(
          (new Date(scan.completed_at).getTime() -
            new Date(scan.started_at).getTime()) /
            1000,
        )
      : null;

  return (
    <div className="border-b border-slate-100 last:border-b-0 dark:border-slate-800">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40"
      >
        <div className="flex items-center gap-4">
          <StatusBadge status={scan.status} />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {scan.scan_type === "full" ? "Full Scan" : "Incremental"}
          </span>
        </div>
        <div className="flex items-center gap-6">
          {duration !== null && (
            <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500">
              {duration}s
            </span>
          )}
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {new Date(scan.started_at).toLocaleString()}
          </span>
          <svg
            className={clsx(
              "h-4 w-4 text-slate-400 transition-transform",
              expanded && "rotate-180",
            )}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      {expanded && (
        <div className="space-y-1.5 px-5 pb-4">
          {scan.phases.map((phase) => (
            <PhaseRow key={phase.name} phase={phase} />
          ))}
          {scan.error_message && (
            <div className="mt-2 rounded-lg bg-red-50 p-3 text-xs text-red-700 dark:bg-red-900/20 dark:text-red-400">
              {scan.error_message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ScanPage() {
  const { projectId, project } = useProjectContext();
  const triggerScan = useTriggerScan(projectId);
  const { data: latestScan } = useLatestScan(projectId);
  const [page, setPage] = useState(1);
  const { data: history, isLoading: historyLoading } = useScanHistory(
    projectId,
    { page, size: 20 },
  );
  const [expandedScanId, setExpandedScanId] = useState<string | null>(null);
  const [scanType, setScanType] = useState<"incremental" | "full">(
    "incremental",
  );

  const isRunning =
    latestScan?.status === "running" || latestScan?.status === "queued";

  function handleTrigger() {
    triggerScan.mutate(scanType === "full");
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Scans</h1>
        <p className="page-subtitle">
          Trigger and monitor permission scans for{" "}
          <span className="font-medium text-slate-700 dark:text-slate-300">
            {project.name}
          </span>
        </p>
      </div>

      {/* Current status + trigger */}
      <div className="card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              Current Status
            </p>
            {latestScan ? (
              <div className="mt-2 flex items-center gap-3">
                <StatusBadge status={latestScan.status} />
                <span className="text-xs text-slate-400 dark:text-slate-500">
                  Started {new Date(latestScan.started_at).toLocaleString()}
                </span>
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-400 dark:text-slate-500">
                No scans run yet
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <select
              value={scanType}
              onChange={(e) =>
                setScanType(e.target.value as "incremental" | "full")
              }
              className="input-base text-sm"
            >
              <option value="incremental">Incremental</option>
              <option value="full">Full Scan</option>
            </select>
            <button
              onClick={handleTrigger}
              disabled={isRunning || triggerScan.isPending}
              className="btn-primary"
            >
              {triggerScan.isPending ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Starting...
                </>
              ) : isRunning ? (
                "Scan in Progress..."
              ) : (
                "Run Scan"
              )}
            </button>
          </div>
        </div>

        {/* Phase progress for latest running scan */}
        {isRunning && latestScan && latestScan.phases.length > 0 && (
          <div className="mt-5 space-y-1.5">
            {latestScan.phases.map((phase) => (
              <PhaseRow key={phase.name} phase={phase} />
            ))}
          </div>
        )}
      </div>

      {/* Scan History */}
      <div className="card">
        <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-800">
          <h2 className="section-title">Scan History</h2>
        </div>

        {historyLoading ? (
          <div className="animate-pulse space-y-3 p-5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-12 rounded-xl bg-slate-100 dark:bg-slate-800"
              />
            ))}
          </div>
        ) : history && history.items.length > 0 ? (
          <>
            {history.items.map((scan) => (
              <ScanHistoryRow
                key={scan.id}
                scan={scan}
                expanded={expandedScanId === scan.id}
                onToggle={() =>
                  setExpandedScanId(
                    expandedScanId === scan.id ? null : scan.id,
                  )
                }
              />
            ))}
            {history.total > history.size && (
              <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 dark:border-slate-800">
                <span className="text-xs text-slate-400">
                  Page {history.page} of{" "}
                  {Math.ceil(history.total / history.size)}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="btn-secondary text-xs"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={
                      page >= Math.ceil(history.total / history.size)
                    }
                    className="btn-secondary text-xs"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="px-5 py-8 text-center text-sm text-slate-400 dark:text-slate-500">
            No scan history yet. Run your first scan above.
          </div>
        )}
      </div>
    </div>
  );
}
