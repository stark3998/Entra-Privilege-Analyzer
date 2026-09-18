import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { usePimSessionDetail, usePimSessionEvents } from "@/api/hooks";
import { useProjectContext } from "@/store/projectContext";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EmptyState } from "@/components/common/EmptyState";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionItem, MotionStagger } from "@/components/common/motion";
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
    active: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300",
    expired: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
    deactivated: "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[session.status] ?? styles.expired}`}>
      {session.is_active && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500" />}
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
      <EmptyState title="PIM session not found" description="This privileged activation session is no longer available." />
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
        className="btn-ghost"
      >
        &larr; Back to PIM Sessions
      </Link>

      {/* Header */}
      <div className="card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">PIM Session Detail</p>
            <h1 className="page-title mt-1">
              {session.principal_display_name}
            </h1>
            {session.principal_upn && (
              <p className="page-subtitle">{session.principal_upn}</p>
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

        <MotionStagger className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MotionItem>
            <dt className="eyebrow">Role</dt>
            <dd className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{session.role_name}</dd>
          </MotionItem>
          <MotionItem>
            <dt className="eyebrow">Activated</dt>
            <dd className="mt-1 text-sm text-slate-900 dark:text-white">
              {new Date(session.activation_time).toLocaleString()}
            </dd>
          </MotionItem>
          <MotionItem>
            <dt className="eyebrow">Expires</dt>
            <dd className="mt-1 text-sm text-slate-900 dark:text-white">
              {new Date(session.expiry_time).toLocaleString()}
            </dd>
          </MotionItem>
          <MotionItem>
            <dt className="eyebrow">Duration</dt>
            <dd className="mt-1 text-sm text-slate-900 dark:text-white">
              {formatDuration(session.duration_minutes)}
            </dd>
          </MotionItem>
        </MotionStagger>

        {/* Activity summary */}
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          <span className="text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-white"><AnimatedNumber value={session.audit_event_count} /></strong> audit events
          </span>
          <span className="text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-white"><AnimatedNumber value={session.sign_in_event_count} /></strong> sign-ins
          </span>
          <span className="text-slate-600 dark:text-slate-400">
            <strong className="text-slate-900 dark:text-white"><AnimatedNumber value={session.anomalies.length} /></strong> anomalies
          </span>
          {session.locations.length > 0 && (
            <span className="text-slate-600 dark:text-slate-400">
              <strong className="text-slate-900 dark:text-white"><AnimatedNumber value={session.locations.length} /></strong> location{session.locations.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      {/* Justification & Ticket & Approval */}
      {(session.justification || session.ticket_info || session.approval_info) && (
        <div className="card p-6">
          <h2 className="section-title">Justification & Approval</h2>
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

      <div className="card p-5">
        <h2 className="section-title">Related</h2>
        <div className="mt-3 space-y-1">
          <Link
            to={`/projects/${projectId}/identities/${session.identity_id}`}
            className="group flex items-center justify-between rounded-xl px-3 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/60"
          >
            <span>
              <span className="block text-sm font-medium text-slate-900 dark:text-white">Identity profile</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">{session.principal_display_name}</span>
            </span>
            <span className="text-slate-400 transition-transform group-hover:translate-x-0.5 dark:text-slate-500">›</span>
          </Link>
          <Link
            to={`/projects/${projectId}/recommendations/${session.identity_id}`}
            className="group flex items-center justify-between rounded-xl px-3 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/60"
          >
            <span>
              <span className="block text-sm font-medium text-slate-900 dark:text-white">Role recommendation</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">Least-privilege analysis for this principal</span>
            </span>
            <span className="text-slate-400 transition-transform group-hover:translate-x-0.5 dark:text-slate-500">›</span>
          </Link>
          <Link
            to={`/projects/${projectId}/drift?search=${encodeURIComponent(session.principal_display_name)}`}
            className="group flex items-center justify-between rounded-xl px-3 py-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/60"
          >
            <span>
              <span className="block text-sm font-medium text-slate-900 dark:text-white">Drift alerts</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">Search anomalous activity for this principal</span>
            </span>
            <span className="text-slate-400 transition-transform group-hover:translate-x-0.5 dark:text-slate-500">›</span>
          </Link>
        </div>
      </div>

      {/* Locations */}
      {session.locations.length > 0 && (
        <div className="card p-6">
          <h2 className="section-title">Sign-in Locations</h2>
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
      <div className="card p-6">
      <h2 className="section-title">
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
                  className="btn-secondary px-3 py-2 text-xs"
                >
                  Previous
                </button>
                <span className="text-xs text-slate-500 dark:text-slate-400">Page {eventsPage} of {eventsTotalPages}</span>
                <button
                  onClick={() => setEventsPage((p) => Math.min(eventsTotalPages, p + 1))}
                  disabled={eventsPage === eventsTotalPages}
                  className="btn-secondary px-3 py-2 text-xs"
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
        <div className="card p-6">
          <h2 className="section-title">
            Actions Performed ({session.unique_actions.length} unique)
          </h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {session.unique_actions.map((action) => (
              <span
                key={action}
                className="chip"
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
