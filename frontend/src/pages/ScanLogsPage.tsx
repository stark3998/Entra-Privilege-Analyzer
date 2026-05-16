import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import clsx from "clsx";
import { useScanDetail, useScanLogs } from "@/api/hooks";
import { useProjectContext } from "@/store/projectContext";
import type { ScanPhase, ScanStreamEvent } from "@/api/types";

const LEVEL_COLORS: Record<string, string> = {
  error: "text-red-400 bg-red-500/10 border-red-800/40",
  warning: "text-amber-400 bg-amber-500/10 border-amber-800/40",
  info: "text-sky-400 bg-sky-500/10 border-sky-800/40",
};

const PHASE_OPTIONS = [
  { value: "", label: "All Phases" },
  { value: "audit_logs", label: "Audit Logs" },
  { value: "sign_in_logs", label: "Sign-In Logs" },
  { value: "directory", label: "Directory" },
  { value: "identity_profiles", label: "Identities" },
];

const LEVEL_OPTIONS = [
  { value: "", label: "All Levels" },
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "error", label: "Error" },
];

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold",
        status === "completed" && "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
        status === "failed" && "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
        status === "running" && "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
        status === "pending" && "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
      )}
    >
      {status}
    </span>
  );
}

function PhaseTimeline({ phases }: { phases: ScanPhase[] }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {phases.map((phase) => {
        const started = phase.started_at ? new Date(phase.started_at) : null;
        const completed = phase.completed_at ? new Date(phase.completed_at) : null;
        const durationSec = started && completed
          ? Math.round((completed.getTime() - started.getTime()) / 1000)
          : null;

        return (
          <div
            key={phase.name}
            className={clsx(
              "rounded-lg border px-3 py-2",
              phase.status === "completed"
                ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800/40 dark:bg-emerald-900/10"
                : phase.status === "failed"
                  ? "border-red-200 bg-red-50 dark:border-red-800/40 dark:bg-red-900/10"
                  : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {phase.name.replace(/_/g, " ")}
              </span>
              <StatusBadge status={phase.status} />
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              {phase.items_processed > 0 && (
                <span>{phase.items_processed.toLocaleString()} items</span>
              )}
              {durationSec !== null && <span>{durationSec}s</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LogRow({ event }: { event: ScanStreamEvent }) {
  const levelClass = LEVEL_COLORS[event.level] || LEVEL_COLORS.info;
  return (
    <tr className="border-b border-slate-100 dark:border-slate-800">
      <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
        {new Date(event.timestamp).toLocaleTimeString()}
      </td>
      <td className="px-3 py-2">
        {event.phase && (
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {event.phase.replace(/_/g, " ")}
          </span>
        )}
      </td>
      <td className="px-3 py-2">
        <span className={clsx("rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase", levelClass)}>
          {event.level}
        </span>
      </td>
      <td className="px-3 py-2 text-sm text-slate-700 dark:text-slate-200">
        {event.message}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
        {typeof event.items_processed === "number" && event.items_processed > 0
          ? event.items_processed.toLocaleString()
          : ""}
      </td>
    </tr>
  );
}

export function ScanLogsPage() {
  const { scanId } = useParams<{ scanId: string }>();
  const { projectId } = useProjectContext();
  const [page, setPage] = useState(1);
  const [levelFilter, setLevelFilter] = useState("");
  const [phaseFilter, setPhaseFilter] = useState("");

  const { data: scan, isLoading: scanLoading } = useScanDetail(scanId || "");
  const { data: logs, isLoading: logsLoading } = useScanLogs(scanId || "", {
    page,
    size: 100,
    level: levelFilter || undefined,
    phase: phaseFilter || undefined,
  });

  if (scanLoading) {
    return (
      <div className="mx-auto max-w-5xl animate-pulse space-y-4 p-6">
        <div className="h-8 w-48 rounded bg-slate-200 dark:bg-slate-700" />
        <div className="h-32 rounded-xl bg-slate-100 dark:bg-slate-800" />
        <div className="h-64 rounded-xl bg-slate-100 dark:bg-slate-800" />
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <p className="text-sm text-slate-500">Scan not found.</p>
        <Link to={`/projects/${projectId}/scan`} className="mt-2 text-sm text-brand-600 hover:underline">
          Back to Scans
        </Link>
      </div>
    );
  }

  const startedAt = new Date(scan.started_at);
  const completedAt = scan.completed_at ? new Date(scan.completed_at) : null;
  const durationSec = completedAt
    ? Math.round((completedAt.getTime() - startedAt.getTime()) / 1000)
    : null;

  const errorCount = logs?.items.filter((e) => e.level === "error").length ?? 0;
  const totalPages = logs ? Math.ceil(logs.total / logs.size) : 1;

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-6">
      {/* Header */}
      <div>
        <Link
          to={`/projects/${projectId}/scan`}
          className="mb-3 inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to Scans
        </Link>

        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-slate-900 dark:text-white">
            Scan {scan.id.slice(0, 8)}...
          </h1>
          <StatusBadge status={scan.status} />
        </div>

        <div className="mt-1 flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
          <span>Started: {startedAt.toLocaleString()}</span>
          {completedAt && <span>Completed: {completedAt.toLocaleString()}</span>}
          {durationSec !== null && <span>Duration: {durationSec}s</span>}
          <span>Type: {scan.scan_type}</span>
        </div>

        {scan.error_message && (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
            {scan.error_message}
          </div>
        )}
      </div>

      {/* Phase Timing */}
      {scan.phases.length > 0 && (
        <div className="card">
          <div className="border-b border-slate-100 px-5 py-3 dark:border-slate-800">
            <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Phase Breakdown</h2>
          </div>
          <div className="p-4">
            <PhaseTimeline phases={scan.phases} />
          </div>
        </div>
      )}

      {/* Error Summary */}
      {errorCount > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-800/40 dark:bg-red-900/10">
          <h3 className="text-sm font-semibold text-red-700 dark:text-red-400">
            {errorCount} Error{errorCount > 1 ? "s" : ""} Detected
          </h3>
          <div className="mt-2 space-y-1.5">
            {logs?.items
              .filter((e) => e.level === "error")
              .slice(0, 5)
              .map((e) => (
                <p key={e.id} className="text-xs text-red-600 dark:text-red-300">
                  [{e.phase?.replace(/_/g, " ") || "scan"}] {e.message}
                </p>
              ))}
            {errorCount > 5 && (
              <p className="text-xs text-red-500 dark:text-red-400">
                + {errorCount - 5} more errors below
              </p>
            )}
          </div>
        </div>
      )}

      {/* Log Table */}
      <div className="card">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Scan Logs {logs && <span className="font-normal text-slate-400">({logs.total} entries)</span>}
          </h2>
          <div className="flex items-center gap-2">
            <select
              value={phaseFilter}
              onChange={(e) => { setPhaseFilter(e.target.value); setPage(1); }}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {PHASE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <select
              value={levelFilter}
              onChange={(e) => { setLevelFilter(e.target.value); setPage(1); }}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {LEVEL_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {logsLoading ? (
          <div className="animate-pulse space-y-2 p-5">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 rounded bg-slate-100 dark:bg-slate-800" />
            ))}
          </div>
        ) : logs && logs.items.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60">
                    <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Time</th>
                    <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Phase</th>
                    <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Level</th>
                    <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Message</th>
                    <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Items</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.items.map((event) => (
                    <LogRow key={event.id} event={event} />
                  ))}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 dark:border-slate-800">
                <span className="text-xs text-slate-400">
                  Page {page} of {totalPages}
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="btn-secondary text-xs"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page >= totalPages}
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
            No log entries found.
          </div>
        )}
      </div>
    </div>
  );
}
