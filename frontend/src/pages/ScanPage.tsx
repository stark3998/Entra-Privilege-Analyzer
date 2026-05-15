import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import {
  useScanHistory,
  useLatestScan,
  useTriggerScan,
  useCancelScan,
  useResumeScan,
  useDelegatedPermissionsCheck,
  useScanLogs,
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
        ) : phase.status === "skipped" ? (
          <div className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700/30">
            <svg className="h-3 w-3 text-slate-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
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

const PHASE_COLORS: Record<string, string> = {
  audit_logs: "bg-blue-500/20 text-blue-300",
  sign_in_logs: "bg-indigo-500/20 text-indigo-300",
  role_assignments: "bg-purple-500/20 text-purple-300",
  identity_profiles: "bg-teal-500/20 text-teal-300",
  action_events: "bg-amber-500/20 text-amber-300",
  pim_sessions: "bg-pink-500/20 text-pink-300",
  access_paths: "bg-orange-500/20 text-orange-300",
};

function ScanLogViewer({
  projectId,
  scanId,
  scanStartedAt,
  liveEvents,
}: {
  projectId: string;
  scanId: string;
  scanStartedAt: string;
  liveEvents?: ScanStreamEvent[];
}) {
  const { data, isLoading } = useScanLogs(projectId, scanId, { size: 500 });
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const startTime = new Date(scanStartedAt).getTime();

  const allEvents = useMemo(() => {
    const persisted: ScanStreamEvent[] = data?.items ?? [];
    const live = liveEvents ?? [];
    const seen = new Set<string>();
    const merged: ScanStreamEvent[] = [];
    for (const e of [...persisted, ...live]) {
      if (!seen.has(e.id)) {
        seen.add(e.id);
        merged.push(e);
      }
    }
    merged.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    return merged;
  }, [data, liveEvents]);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [allEvents, autoScroll]);

  function handleScroll() {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  }

  if (isLoading) {
    return (
      <div className="mt-3 rounded-lg bg-slate-950 px-4 py-6 text-center text-xs text-slate-400">
        Loading logs...
      </div>
    );
  }

  if (allEvents.length === 0) {
    return (
      <div className="mt-3 rounded-lg bg-slate-950 px-4 py-6 text-center text-xs text-slate-400">
        No logs available for this scan.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="mt-3 max-h-96 space-y-0.5 overflow-y-auto rounded-lg bg-slate-950 p-2"
    >
      {allEvents.map((event) => {
        const elapsed = (
          (new Date(event.timestamp).getTime() - startTime) /
          1000
        ).toFixed(1);
        const phaseStyle = event.phase
          ? PHASE_COLORS[event.phase] ?? "bg-slate-700/50 text-slate-300"
          : null;
        return (
          <div
            key={event.id}
            className="flex items-start gap-2 rounded px-2 py-1 text-xs hover:bg-slate-900"
          >
            <span className="w-16 shrink-0 tabular-nums text-slate-500">
              +{elapsed}s
            </span>
            {phaseStyle && (
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${phaseStyle}`}
              >
                {event.phase!.replace(/_/g, " ")}
              </span>
            )}
            {event.level === "error" ? (
              <span className="shrink-0 text-red-400">&#9679;</span>
            ) : event.level === "warning" ? (
              <span className="shrink-0 text-amber-400">&#9650;</span>
            ) : (
              <span className="shrink-0 text-blue-400">&#9679;</span>
            )}
            <span
              className={clsx(
                "flex-1",
                event.level === "error" && "text-red-300",
                event.level === "warning" && "text-amber-200",
                event.level === "info" && "text-slate-200",
              )}
            >
              {event.message}
            </span>
            {typeof event.items_processed === "number" &&
              event.items_processed > 0 && (
                <span className="shrink-0 tabular-nums text-slate-500">
                  {event.items_processed.toLocaleString()}
                </span>
              )}
          </div>
        );
      })}
    </div>
  );
}

function ScanHistoryRow({
  scan,
  expanded,
  onToggle,
  projectId,
}: {
  scan: ScanRecord;
  expanded: boolean;
  onToggle: () => void;
  projectId: string;
}) {
  const [showLogs, setShowLogs] = useState(false);
  const resumeScan = useResumeScan(projectId);
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
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowLogs(!showLogs)}
              className="flex items-center gap-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {showLogs ? "Hide Logs" : "View Logs"}
            </button>
            {scan.status === "failed" && (
              <button
                type="button"
                onClick={() => resumeScan.mutate(scan.id)}
                disabled={resumeScan.isPending}
                title="Resume from where it left off — completed phases will be skipped"
                className="flex items-center gap-1.5 text-xs font-medium text-emerald-600 hover:text-emerald-700 disabled:opacity-50 dark:text-emerald-400 dark:hover:text-emerald-300"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {resumeScan.isPending ? "Resuming..." : "Resume Scan"}
              </button>
            )}
          </div>
          {showLogs && (
            <ScanLogViewer
              projectId={projectId}
              scanId={scan.id}
              scanStartedAt={scan.started_at}
            />
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
                projectId={projectId}
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
