import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { usePimSessionDetail, usePimSessionEvents } from "@/api/hooks";
import { useProjectContext } from "@/store/projectContext";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { SessionTimeline } from "@/components/pim-sessions/SessionTimeline";
import { AnomalyList } from "@/components/pim-sessions/AnomalyList";
import type { PimSession } from "@/api/types";

function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function StatusBadge({ session }: { session: PimSession }) {
  const styles: Record<string, string> = {
    active: "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300",
    expired: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
    deactivated: "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[session.status] ?? styles.expired}`}>
      {session.is_active && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />}
      {session.status}
    </span>
  );
}

function ScopeBadge({ scope }: { scope: string }) {
  const isEntra = scope === "entra_directory";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
      isEntra
        ? "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-300"
        : "bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-300"
    }`}>
      {isEntra ? "Entra ID" : "Azure RBAC"}
    </span>
  );
}

export function PimSessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { projectId } = useProjectContext();
  const [eventsPage, setEventsPage] = useState(1);

  const { data: session, isLoading } = usePimSessionDetail(id ?? "");
  const { data: eventsData, isLoading: eventsLoading } = usePimSessionEvents(id ?? "", { page: eventsPage, size: 30 });

  if (isLoading) return <LoadingSpinner />;
  if (!session) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-12 text-center dark:border-slate-700 dark:bg-slate-800">
        <p className="text-slate-500 dark:text-slate-400">PIM session not found.</p>
      </div>
    );
  }

  const events = eventsData?.items ?? [];
  const eventsTotal = eventsData?.total ?? 0;
  const eventsTotalPages = Math.max(1, Math.ceil(eventsTotal / 30));

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to={`/projects/${projectId}/pim-sessions`}
        className="inline-flex items-center text-sm text-indigo-600 hover:text-indigo-800 dark:text-indigo-400"
      >
        &larr; Back to PIM Sessions
      </Link>

      {/* Header */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">
              {session.principal_display_name}
            </h1>
            {session.principal_upn && (
              <p className="text-sm text-slate-500 dark:text-slate-400">{session.principal_upn}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge session={session} />
            <ScopeBadge scope={session.session_scope} />
            {session.risk_score > 0 && (
              <SeverityBadge severity={session.risk_score >= 10 ? "high" : session.risk_score >= 3 ? "medium" : "low"} />
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">Role</dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{session.role_name}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">Activated</dt>
            <dd className="mt-1 text-sm text-slate-900 dark:text-white">
              {new Date(session.activation_time).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">Expires</dt>
            <dd className="mt-1 text-sm text-slate-900 dark:text-white">
              {new Date(session.expiry_time).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">Duration</dt>
            <dd className="mt-1 text-sm text-slate-900 dark:text-white">
              {formatDuration(session.duration_minutes)}
            </dd>
          </div>
        </div>

        {/* Activity summary */}
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          <span className="text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-white">{session.audit_event_count}</strong> audit events
          </span>
          <span className="text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-white">{session.sign_in_event_count}</strong> sign-ins
          </span>
          <span className="text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-white">{session.anomalies.length}</strong> anomalies
          </span>
          {session.locations.length > 0 && (
            <span className="text-slate-600 dark:text-slate-400">
              <strong className="text-slate-900 dark:text-white">{session.locations.length}</strong> location{session.locations.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      {/* Justification & Ticket & Approval */}
      {(session.justification || session.ticket_info || session.approval_info) && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Justification & Approval</h2>
          <div className="mt-3 space-y-2 text-sm">
            {session.justification && (
              <div>
                <span className="font-medium text-slate-500 dark:text-slate-400">Justification: </span>
                <span className="text-slate-900 dark:text-white">{session.justification}</span>
              </div>
            )}
            {session.ticket_info?.ticket_number && (
              <div>
                <span className="font-medium text-slate-500 dark:text-slate-400">Ticket: </span>
                <span className="text-slate-900 dark:text-white">
                  {session.ticket_info.ticket_number}
                  {session.ticket_info.ticket_system && ` (${session.ticket_info.ticket_system})`}
                </span>
              </div>
            )}
            {session.approval_info?.approval_status && (
              <div>
                <span className="font-medium text-slate-500 dark:text-slate-400">Approval: </span>
                <span className="text-slate-900 dark:text-white">
                  {session.approval_info.approval_status}
                  {session.approval_info.approver_display_name && ` by ${session.approval_info.approver_display_name}`}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Anomalies */}
      {session.anomalies.length > 0 && <AnomalyList anomalies={session.anomalies} />}

      {/* Locations */}
      {session.locations.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Sign-in Locations</h2>
          <div className="mt-3 space-y-1">
            {session.locations.map((loc, i) => (
              <div key={i} className="flex items-center gap-3 text-sm text-slate-700 dark:text-slate-300">
                <span className="font-mono text-xs text-slate-500">{loc.ip_address ?? "—"}</span>
                <span>{[loc.city, loc.state, loc.country].filter(Boolean).join(", ") || "Unknown"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Session Timeline */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
          Session Activity Timeline ({eventsTotal} events)
        </h2>
        {eventsLoading ? (
          <LoadingSpinner />
        ) : events.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">No events recorded during this session.</p>
        ) : (
          <>
            <SessionTimeline events={events} session={session} />
            {eventsTotalPages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <button
                  onClick={() => setEventsPage((p) => Math.max(1, p - 1))}
                  disabled={eventsPage === 1}
                  className="rounded border px-3 py-1 text-xs disabled:opacity-50 dark:border-slate-600 dark:text-white"
                >
                  Previous
                </button>
                <span className="text-xs text-slate-500">Page {eventsPage} of {eventsTotalPages}</span>
                <button
                  onClick={() => setEventsPage((p) => Math.min(eventsTotalPages, p + 1))}
                  disabled={eventsPage === eventsTotalPages}
                  className="rounded border px-3 py-1 text-xs disabled:opacity-50 dark:border-slate-600 dark:text-white"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Unique actions */}
      {session.unique_actions.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
            Actions Performed ({session.unique_actions.length} unique)
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {session.unique_actions.map((action) => (
              <span
                key={action}
                className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-300"
              >
                {action}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
