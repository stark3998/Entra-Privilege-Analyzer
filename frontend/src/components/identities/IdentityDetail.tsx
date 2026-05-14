// frontend/src/components/identities/IdentityDetail.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import type { IdentityProfile, IdentityType, CurrentRole, ObservedAction } from "@/api/types";
import { useIdentityPimSessions } from "@/api/hooks";
import { ActionTimeline } from "./ActionTimeline";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface IdentityDetailProps {
  identity: IdentityProfile;
}

/** Color map for identity type badges. */
const TYPE_COLORS: Record<IdentityType, { bg: string; dot: string }> = {
  User: { bg: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300", dot: "bg-blue-500" },
  ServicePrincipal: { bg: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300", dot: "bg-purple-500" },
  ManagedIdentity: { bg: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300", dot: "bg-emerald-500" },
  Group: { bg: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300", dot: "bg-amber-500" },
};

/** Color map for role assignment type badges. */
const ASSIGNMENT_COLORS: Record<string, string> = {
  direct: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  group: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  pim: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="card px-4 py-3">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p
        className={clsx(
          "mt-1 text-xl font-bold",
          color ?? "text-slate-900 dark:text-white",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function RiskScoreColor(score: number): string {
  if (score > 70) return "text-red-600 dark:text-red-400";
  if (score > 40) return "text-amber-600 dark:text-amber-400";
  return "text-emerald-600 dark:text-emerald-400";
}

function CurrentRolesTable({ roles }: { roles: CurrentRole[] }) {
  if (roles.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-slate-400 dark:text-slate-500">
        No roles assigned
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-800/50">
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Role
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Scope
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Assignment
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Permanent
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {roles.map((role) => (
            <tr key={role.role_id}>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm font-medium text-slate-900 dark:text-white">
                {role.role_name}
              </td>
              <td className="max-w-xs truncate px-4 py-2.5 text-sm text-slate-600 dark:text-slate-400" title={role.scope}>
                {role.scope}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm">
                <span
                  className={clsx(
                    "inline-flex rounded px-1.5 py-0.5 text-xs font-medium",
                    ASSIGNMENT_COLORS[role.assignment_type.toLowerCase()] ??
                      "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                  )}
                >
                  {role.assignment_type}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm">
                {role.is_permanent ? (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400">
                    <svg
                      className="h-3.5 w-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                    Permanent
                  </span>
                ) : (
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    Time-limited
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ObservedActionsTable({ actions }: { actions: ObservedAction[] }) {
  if (actions.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-slate-400 dark:text-slate-500">
        No observed actions
      </p>
    );
  }

  // Sort by count descending
  const sorted = [...actions].sort((a, b) => b.count - a.count);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
        <thead>
          <tr className="bg-slate-50 dark:bg-slate-800/50">
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Action
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Resource
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Count
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              First Seen
            </th>
            <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Last Seen
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {sorted.map((action, idx) => (
            <tr key={`${action.action}-${idx}`}>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm font-medium text-slate-900 dark:text-white">
                {action.action}
              </td>
              <td className="max-w-xs truncate px-4 py-2.5 text-sm text-slate-600 dark:text-slate-400" title={action.resource ?? undefined}>
                {action.resource ?? (
                  <span className="text-slate-400 dark:text-slate-500">--</span>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm tabular-nums text-slate-700 dark:text-slate-300">
                {action.count.toLocaleString()}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm text-slate-500 dark:text-slate-400">
                {formatRelativeTime(action.first_seen)}
              </td>
              <td className="whitespace-nowrap px-4 py-2.5 text-sm text-slate-500 dark:text-slate-400">
                {formatRelativeTime(action.last_seen)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Full detail view for a single identity profile.
 * Displays header, stats, current roles, observed actions, and action timeline.
 */
const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  expired: "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
  deactivated: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

function PimSessionsTab({ identityId }: { identityId: string }) {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const size = 10;
  const { data, isLoading } = useIdentityPimSessions(identityId, { page, size });

  const sessions = data?.items ?? [];
  const total = data?.total ?? 0;

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-3 py-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 rounded bg-slate-100 dark:bg-slate-800" />
        ))}
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-slate-400 dark:text-slate-500">
        No PIM session activations found for this identity.
      </p>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
          <thead>
            <tr className="bg-slate-50 dark:bg-slate-800/50">
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Role</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Status</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Activated</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Duration</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Events</th>
              <th className="px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400">Anomalies</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {sessions.map((s) => (
              <tr
                key={s.id}
                className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50"
                onClick={() => navigate(`../pim-sessions/${s.id}`)}
              >
                <td className="whitespace-nowrap px-4 py-2.5 text-sm font-medium text-slate-900 dark:text-white">
                  {s.role_name}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">
                  <span className={clsx("inline-flex rounded px-1.5 py-0.5 text-xs font-medium", STATUS_STYLES[s.status] ?? STATUS_STYLES.expired)}>
                    {s.status}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm text-slate-500 dark:text-slate-400">
                  {formatRelativeTime(s.activation_time)}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm tabular-nums text-slate-700 dark:text-slate-300">
                  {s.duration_minutes < 60
                    ? `${s.duration_minutes}m`
                    : `${(s.duration_minutes / 60).toFixed(1)}h`}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm tabular-nums text-slate-700 dark:text-slate-300">
                  {s.total_event_count}
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm">
                  {s.anomalies.length > 0 ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-300">
                      {s.anomalies.length}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > size && (
        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 dark:border-slate-700">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {(page - 1) * size + 1}–{Math.min(page * size, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="btn-secondary text-xs disabled:opacity-40">Prev</button>
            <button type="button" disabled={page * size >= total} onClick={() => setPage(page + 1)} className="btn-secondary text-xs disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function IdentityDetail({ identity }: IdentityDetailProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <h1 className="page-title">{identity.display_name}</h1>
            <span className={clsx("badge", TYPE_COLORS[identity.identity_type].bg)}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", TYPE_COLORS[identity.identity_type].dot)} />
              {identity.identity_type}
            </span>
          </div>
          <div className="mt-1 space-y-0.5">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Object ID:{" "}
              <span className="font-mono text-xs">{identity.object_id}</span>
            </p>
            {identity.upn && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                UPN: {identity.upn}
              </p>
            )}
            {identity.app_id && (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                App ID:{" "}
                <span className="font-mono text-xs">{identity.app_id}</span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          label="Risk Score"
          value={identity.risk_score}
          color={RiskScoreColor(identity.risk_score)}
        />
        <StatCard label="Total Actions" value={identity.action_count.toLocaleString()} />
        <StatCard label="Roles" value={identity.current_roles.length} />
        <StatCard
          label="First Seen"
          value={formatRelativeTime(identity.first_seen)}
        />
        <StatCard
          label="Last Seen"
          value={formatRelativeTime(identity.last_seen)}
        />
      </div>

      <section>
        <h2 className="section-title mb-3">Current Roles</h2>
        <div className="card overflow-hidden">
          <CurrentRolesTable roles={identity.current_roles} />
        </div>
      </section>

      <section>
        <h2 className="section-title mb-3">PIM Sessions</h2>
        <div className="card overflow-hidden">
          <PimSessionsTab identityId={identity.id} />
        </div>
      </section>

      <section>
        <h2 className="section-title mb-3">Observed Actions</h2>
        <div className="card overflow-hidden">
          <ObservedActionsTable actions={identity.observed_actions} />
        </div>
      </section>

      <section>
        <h2 className="section-title mb-3">Action Timeline</h2>
        <ActionTimeline identityId={identity.id} />
      </section>
    </div>
  );
}
