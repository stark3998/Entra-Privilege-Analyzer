import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  useScanHistory,
  useLatestScan,
  useTriggerScan,
  useCancelScan,
  useDelegatedPermissionsCheck,
  pollScanEvents,
} from "@/api/projectHooks";
import { useProjectContext } from "@/store/projectContext";
import type { ScanRecord, ScanPhase, ScanStreamEvent } from "@/api/types";

const POLL_INTERVAL_MS = 2000;

interface PollDebugState {
  startedAt: string;
  pollCount: number;
  eventCount: number;
  lastPollAt: string | null;
  lastCursor: string | null;
  lastScanStatus: string | null;
  lastError: string | null;
  completed: boolean;
}

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

function AuthModeBadge({ mode }: { mode: string }) {
  if (mode === "delegated") {
    return (
      <span className="badge bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400">
        Delegated
      </span>
    );
  }
  return (
    <span className="badge bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
      App
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
          <AuthModeBadge mode={scan.auth_mode ?? "app"} />
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

function buildSnapshotStreamEvent(scan: ScanRecord): ScanStreamEvent {
  const runningPhase =
    scan.phases.find((phase) => phase.status === "running")?.name ?? null;

  return {
    id: `${scan.project_id}:${scan.id}:frontend-snapshot`,
    type: "scan.snapshot",
    message:
      scan.status === "running" || scan.status === "queued"
        ? `${scan.scan_type === "full" ? "Full" : "Incremental"} scan is currently ${scan.status}.`
        : `${scan.scan_type === "full" ? "Full" : "Incremental"} scan last ended with status ${scan.status}.`,
    project_id: scan.project_id,
    scan_id: scan.id,
    level: scan.status === "failed" ? "error" : "info",
    phase: runningPhase,
    status: scan.status,
    items_processed: null,
    timestamp: scan.started_at,
    details: {
      snapshot: true,
      auth_mode: scan.auth_mode,
      scan_type: scan.scan_type,
      phases: scan.phases,
      completed_at: scan.completed_at,
      error_message: scan.error_message,
    },
  };
}

export function ScanPage() {
  const { projectId, project } = useProjectContext();
  const triggerScan = useTriggerScan(projectId);
  const cancelScan = useCancelScan(projectId);
  const { data: latestScan } = useLatestScan(projectId);
  const [page, setPage] = useState(1);
  const { data: history, isLoading: historyLoading } = useScanHistory(
    projectId,
    { page, size: 20 },
  );
  const [expandedScanId, setExpandedScanId] = useState<string | null>(null);
  const [streamEvents, setStreamEvents] = useState<ScanStreamEvent[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [pollDebug, setPollDebug] = useState<PollDebugState | null>(null);
  const [scanType, setScanType] = useState<"incremental" | "full">(
    "incremental",
  );

  const hasAppCredentials = !!(project.client_id);
  const [authMode, setAuthMode] = useState<"app" | "delegated">(
    hasAppCredentials ? "app" : "delegated",
  );

  const { data: permCheck, isLoading: permCheckLoading } =
    useDelegatedPermissionsCheck(projectId, authMode === "delegated");

  const isRunning =
    latestScan?.status === "running" || latestScan?.status === "queued";

  // Ref keeps the cursor across poll ticks without triggering re-renders.
  const cursorRef = useRef<string | null>(null);

  // Poll for scan events instead of SSE (Envoy buffers SSE in Container Apps).
  const doPoll = useCallback(
    async (scanId: string, debug: PollDebugState) => {
      try {
        const res = await pollScanEvents(projectId, scanId, cursorRef.current);
        debug.pollCount += 1;
        debug.lastPollAt = new Date().toISOString();
        debug.lastScanStatus = res.scan_status;

        if (res.events.length > 0) {
          debug.eventCount += res.events.length;
          setStreamEvents((prev) => [...prev, ...res.events].slice(-80));
        }
        if (res.cursor) {
          cursorRef.current = res.cursor;
          debug.lastCursor = res.cursor;
        }
        if (res.scan_status === "completed" || res.scan_status === "failed") {
          debug.completed = true;
        }
        debug.lastError = null;
        setPollDebug({ ...debug });
      } catch (err: unknown) {
        debug.lastError = err instanceof Error ? err.message : "Poll failed";
        setPollDebug({ ...debug });
      }
    },
    [projectId],
  );

  useEffect(() => {
    if (!projectId || !latestScan?.id || !isRunning) {
      return;
    }

    // Reset state for a fresh scan.
    setStreamEvents([buildSnapshotStreamEvent(latestScan)]);
    setStreamError(null);
    cursorRef.current = null;

    const debug: PollDebugState = {
      startedAt: new Date().toISOString(),
      pollCount: 0,
      eventCount: 0,
      lastPollAt: null,
      lastCursor: null,
      lastScanStatus: null,
      lastError: null,
      completed: false,
    };
    setPollDebug(debug);

    let cancelled = false;

    // Kick off the first poll immediately, then schedule at interval.
    const scanId = latestScan.id;
    doPoll(scanId, debug);

    const interval = window.setInterval(() => {
      if (cancelled || debug.completed) {
        window.clearInterval(interval);
        return;
      }
      doPoll(scanId, debug);
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [projectId, latestScan?.id, isRunning, doPoll]);

  function handleTrigger() {
    triggerScan.mutate({ full: scanType === "full", authMode });
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
            {/* Auth mode toggle */}
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-700">
              <button
                onClick={() => setAuthMode("app")}
                disabled={!hasAppCredentials}
                title={
                  hasAppCredentials
                    ? "Use project app registration credentials"
                    : "No app credentials configured for this project"
                }
                className={clsx(
                  "rounded-l-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  authMode === "app"
                    ? "bg-blue-600 text-white"
                    : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800",
                  !hasAppCredentials && "cursor-not-allowed opacity-40",
                )}
              >
                App Credentials
              </button>
              <button
                onClick={() => setAuthMode("delegated")}
                className={clsx(
                  "rounded-r-lg px-3 py-1.5 text-xs font-medium transition-colors",
                  authMode === "delegated"
                    ? "bg-purple-600 text-white"
                    : "text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800",
                )}
              >
                My Credentials
              </button>
            </div>

            <select
              value={scanType}
              onChange={(e) =>
                setScanType(e.target.value as "incremental" | "full")
              }
              className="input-base text-sm"
              title="Select scan type"
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
            {isRunning && latestScan && (
              <button
                onClick={() => cancelScan.mutate(latestScan.id)}
                disabled={cancelScan.isPending}
                className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40"
              >
                {cancelScan.isPending ? "Cancelling..." : "Cancel Scan"}
              </button>
            )}
          </div>
        </div>

        {/* Delegated mode info banner */}
        {authMode === "delegated" && (
          <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50 p-3 dark:border-purple-800 dark:bg-purple-900/20">
            <p className="text-xs text-purple-700 dark:text-purple-300">
              Scan will use your Entra ID permissions via delegated access (OBO flow).
              You need sufficient admin roles (e.g., Global Reader) to read directory data.
              Some data may be unavailable if your permissions are limited.
            </p>
            {permCheckLoading && (
              <p className="mt-1 text-xs text-purple-500 dark:text-purple-400">
                Checking your permissions...
              </p>
            )}
            {permCheck && !permCheck.sufficient && (
              <div className="mt-2">
                <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
                  Missing permissions: {permCheck.missing_scopes.join(", ")}
                </p>
                <p className="mt-0.5 text-xs text-purple-600 dark:text-purple-400">
                  The scan may return partial results. Ask your admin to grant delegated permissions and admin consent.
                </p>
              </div>
            )}
            {permCheck?.error && (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                Permission check failed: {permCheck.error}
              </p>
            )}
            {permCheck && permCheck.sufficient && (
              <p className="mt-1 text-xs text-emerald-600 dark:text-emerald-400">
                All required permissions are available.
              </p>
            )}
          </div>
        )}

        {/* Phase progress for latest running scan */}
        {isRunning && latestScan && latestScan.phases.length > 0 && (
          <div className="mt-5 space-y-1.5">
            {latestScan.phases.map((phase) => (
              <PhaseRow key={phase.name} phase={phase} />
            ))}
          </div>
        )}

        {(isRunning || streamEvents.length > 0 || streamError) && (
          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-950 px-4 py-3 text-slate-100 dark:border-slate-800">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Live Activity</p>
                <p className="text-xs text-slate-400">
                  Polling scan phases, Graph retries, and action ingest progress.
                </p>
              </div>
              {isRunning && (
                <span className="badge bg-emerald-500/10 text-emerald-300">Polling</span>
              )}
            </div>

            {streamError && (
              <div className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {streamError}
              </div>
            )}

            <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
              {streamEvents.length === 0 ? (
                <div className="rounded-lg bg-slate-900 px-3 py-2 text-xs text-slate-400">
                  Waiting for live events...
                </div>
              ) : (
                streamEvents.map((event) => (
                  <div
                    key={event.id}
                    className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-3 text-xs">
                      <span
                        className={clsx(
                          "font-medium uppercase tracking-wide",
                          event.level === "error" && "text-red-300",
                          event.level === "warning" && "text-amber-300",
                          event.level === "info" && "text-sky-300",
                        )}
                      >
                        {event.phase ? event.phase.replace(/_/g, " ") : event.type}
                      </span>
                      <span className="text-slate-500">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-100">{event.message}</p>
                    {typeof event.items_processed === "number" && event.items_processed > 0 && (
                      <p className="mt-1 text-xs text-slate-400">
                        {event.items_processed.toLocaleString()} items processed
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-300">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 md:grid-cols-4">
                <span>ui events: {streamEvents.length}</span>
                <span>polls: {pollDebug?.pollCount ?? 0}</span>
                <span>recv events: {pollDebug?.eventCount ?? 0}</span>
                <span>scan status: {pollDebug?.lastScanStatus ?? "-"}</span>
                <span>done: {pollDebug?.completed ? "yes" : "no"}</span>
                <span>last poll: {pollDebug?.lastPollAt ? new Date(pollDebug.lastPollAt).toLocaleTimeString() : "-"}</span>
                <span>cursor: {pollDebug?.lastCursor ? pollDebug.lastCursor.slice(11, 23) : "-"}</span>
                <span>last error: {pollDebug?.lastError ?? "-"}</span>
              </div>
            </div>
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
