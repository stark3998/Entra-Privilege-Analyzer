// frontend/src/components/identities/IdentityDetail.tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import clsx from "clsx";
import type { IdentityProfile, IdentityType, CurrentRole, ObservedAction } from "@/api/types";
import { useIdentityPimSessions, useIdentityAccessPaths } from "@/api/hooks";
import { ActionTimeline } from "./ActionTimeline";
import { AccessPathGraph } from "@/components/access-paths/AccessPathGraph";
import { AccessPathCard } from "@/components/access-paths/AccessPathCard";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { MotionStagger, MotionItem, motion } from "@/components/common/motion";
import { useProjectContext } from "@/store/projectContext";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

interface IdentityDetailProps {
  identity: IdentityProfile;
}

const TYPE_COLORS: Record<IdentityType, { badge: string; dot: string; avatar: string }> = {
  User: {
    badge: "bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300",
    dot: "bg-brand-500",
    avatar: "bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-950/40 dark:text-brand-300 dark:ring-brand-900/60",
  },
  ServicePrincipal: {
    badge: "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300",
    dot: "bg-violet-500",
    avatar: "bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-950/40 dark:text-violet-300 dark:ring-violet-900/60",
  },
  ManagedIdentity: {
    badge: "bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300",
    dot: "bg-teal-500",
    avatar: "bg-teal-50 text-teal-700 ring-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:ring-teal-900/60",
  },
  Group: {
    badge: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    dot: "bg-amber-500",
    avatar: "bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900/60",
  },
};

const ASSIGNMENT_COLORS: Record<string, string> = {
  direct: "bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300",
  group: "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300",
  pim: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
};

const STATUS_STYLES: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  expired: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  deactivated: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
};

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "ID";
}

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, score));
}

function riskTone(score: number) {
  if (score > 70) {
    return {
      label: "High risk",
      text: "text-red-600 dark:text-red-400",
      bar: "bg-red-500",
      surface: "bg-red-50 dark:bg-red-950/30",
    };
  }
  if (score > 40) {
    return {
      label: "Moderate risk",
      text: "text-amber-600 dark:text-amber-400",
      bar: "bg-amber-500",
      surface: "bg-amber-50 dark:bg-amber-950/30",
    };
  }
  return {
    label: "Low risk",
    text: "text-emerald-600 dark:text-emerald-400",
    bar: "bg-emerald-500",
    surface: "bg-emerald-50 dark:bg-emerald-950/30",
  };
}

function RiskScoreRing({ score }: { score: number }) {
  const tone = riskTone(score);
  const clamped = clampScore(score);
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className={clsx("flex items-center gap-4 rounded-2xl p-4", tone.surface)}>
      <div className="relative h-28 w-28">
        <svg className="h-28 w-28 -rotate-90" viewBox="0 0 112 112" aria-hidden="true">
          <circle
            cx="56"
            cy="56"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="10"
            className="text-white/80 dark:text-slate-800"
          />
          <motion.circle
            cx="56"
            cy="56"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="10"
            strokeLinecap="round"
            className={tone.text}
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <AnimatedNumber
            value={clamped}
            className={clsx("text-3xl font-bold tabular-nums", tone.text)}
          />
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Risk
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <p className={clsx("text-sm font-semibold", tone.text)}>{tone.label}</p>
        <p className="mt-1 max-w-[14rem] text-sm text-slate-500 dark:text-slate-400">
          Composite score from role exposure, observed activity, and anomaly signals.
        </p>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  animated = false,
}: {
  label: string;
  value: string | number;
  color?: string;
  animated?: boolean;
}) {
  return (
    <div className="card p-4">
      <p className="eyebrow">{label}</p>
      <p
        className={clsx(
          "mt-2 text-2xl font-bold tabular-nums",
          color ?? "text-slate-900 dark:text-white",
        )}
      >
        {animated && typeof value === "number" ? <AnimatedNumber value={value} /> : value}
      </p>
    </div>
  );
}

function CurrentRolesTable({ roles }: { roles: CurrentRole[] }) {
  if (roles.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
        No roles assigned
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800">
        <thead>
          <tr className="bg-slate-50/80 dark:bg-slate-800/30">
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Role
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Scope
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Assignment
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Access Window
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
          {roles.map((role) => (
            <tr
              key={`${role.role_id}-${role.scope}`}
              className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/60"
            >
              <td className="whitespace-nowrap px-4 py-3.5 text-sm font-medium text-slate-900 dark:text-white">
                {role.role_name}
              </td>
              <td className="max-w-xs truncate px-4 py-3.5 text-sm text-slate-600 dark:text-slate-400" title={role.scope}>
                {role.scope}
              </td>
              <td className="whitespace-nowrap px-4 py-3.5 text-sm">
                <span
                  className={clsx(
                    "badge capitalize",
                    ASSIGNMENT_COLORS[role.assignment_type.toLowerCase()] ??
                      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
                  )}
                >
                  {role.assignment_type}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-3.5 text-sm">
                {role.is_permanent ? (
                  <span className="badge bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
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
                  <span className="badge bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
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
      <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
        No observed actions
      </p>
    );
  }

  const sorted = [...actions].sort((a, b) => b.count - a.count);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800">
        <thead>
          <tr className="bg-slate-50/80 dark:bg-slate-800/30">
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Action
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Resource
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Count
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              First Seen
            </th>
            <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Last Seen
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
          {sorted.map((action, idx) => (
            <tr
              key={`${action.action}-${idx}`}
              className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/60"
            >
              <td className="whitespace-nowrap px-4 py-3.5 text-sm font-medium text-slate-900 dark:text-white">
                {action.action}
              </td>
              <td className="max-w-xs truncate px-4 py-3.5 text-sm text-slate-600 dark:text-slate-400" title={action.resource ?? undefined}>
                {action.resource ?? (
                  <span className="text-slate-400 dark:text-slate-500">--</span>
                )}
              </td>
              <td className="whitespace-nowrap px-4 py-3.5 text-sm">
                <span className="chip tabular-nums">
                  <AnimatedNumber value={action.count} />
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-3.5 text-sm text-slate-500 dark:text-slate-400">
                {formatRelativeTime(action.first_seen)}
              </td>
              <td className="whitespace-nowrap px-4 py-3.5 text-sm text-slate-500 dark:text-slate-400">
                {formatRelativeTime(action.last_seen)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PimSessionsTab({ identityId }: { identityId: string }) {
  const navigate = useNavigate();
  const { projectId } = useProjectContext();
  const [page, setPage] = useState(1);
  const size = 10;
  const { data, isLoading } = useIdentityPimSessions(identityId, { page, size });

  const sessions = data?.items ?? [];
  const total = data?.total ?? 0;

  if (isLoading) {
    return (
      <div className="space-y-3 p-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="skeleton h-12" />
        ))}
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-slate-400 dark:text-slate-500">
        No PIM session activations found for this identity.
      </p>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-800">
          <thead>
            <tr className="bg-slate-50/80 dark:bg-slate-800/30">
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Role</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Status</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Activated</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Duration</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Events</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">Anomalies</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
            {sessions.map((s) => (
              <tr
                key={s.id}
                className="cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/60"
                onClick={() => navigate(`/projects/${projectId}/pim-sessions/${s.id}`)}
              >
                <td className="whitespace-nowrap px-4 py-3.5 text-sm font-medium text-slate-900 dark:text-white">
                  {s.role_name}
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-sm">
                  <span className={clsx("badge capitalize", STATUS_STYLES[s.status] ?? STATUS_STYLES.expired)}>
                    {s.status}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-sm text-slate-500 dark:text-slate-400">
                  {formatRelativeTime(s.activation_time)}
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-sm tabular-nums text-slate-700 dark:text-slate-300">
                  {s.duration_minutes < 60
                    ? `${s.duration_minutes}m`
                    : `${(s.duration_minutes / 60).toFixed(1)}h`}
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-sm tabular-nums text-slate-700 dark:text-slate-300">
                  <AnimatedNumber value={s.total_event_count} />
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-sm">
                  {s.anomalies.length > 0 ? (
                    <span className="badge bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300">
                      <AnimatedNumber value={s.anomalies.length} />
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400 dark:text-slate-500">--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {total > size && (
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/50 px-4 py-3 dark:border-slate-800 dark:bg-slate-800/20">
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            {(page - 1) * size + 1}–{Math.min(page * size, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="btn-secondary px-3 py-1.5 text-xs">Prev</button>
            <button type="button" disabled={page * size >= total} onClick={() => setPage(page + 1)} className="btn-secondary px-3 py-1.5 text-xs">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}

function AccessPathsSection({ identityId }: { identityId: string }) {
  const { data, isLoading } = useIdentityAccessPaths(identityId);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const paths = data?.paths ?? [];
  const total = data?.total_paths ?? 0;
  const highestRisk = data?.highest_risk ?? "none";

  if (isLoading) {
    return (
      <section>
        <h2 className="section-title mb-3">Privilege Escalation Paths</h2>
        <div className="card p-6">
          <div className="skeleton h-4 w-48" />
          <div className="mt-4 grid gap-3 lg:grid-cols-[18rem_minmax(0,1fr)]">
            <div className="space-y-2">
              <div className="skeleton h-16" />
              <div className="skeleton h-16" />
            </div>
            <div className="skeleton h-56" />
          </div>
        </div>
      </section>
    );
  }

  if (total === 0) {
    return (
      <section>
        <h2 className="section-title mb-3">Privilege Escalation Paths</h2>
        <div className="card p-6 text-center text-sm text-slate-400 dark:text-slate-500">
          No privilege escalation paths detected
        </div>
      </section>
    );
  }

  const displayPaths = selectedIdx !== null && paths[selectedIdx] ? [paths[selectedIdx]] : paths;

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="section-title">Privilege Escalation Paths</h2>
        <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
          <AnimatedNumber value={total} />
          paths
        </span>
        {highestRisk !== "none" && (
          <SeverityBadge severity={highestRisk as "critical" | "high" | "medium"} />
        )}
      </div>
      <div className="card overflow-hidden">
        <div className="flex flex-col lg:flex-row">
          <div className="max-h-[440px] shrink-0 space-y-2 overflow-y-auto border-b border-slate-100 p-3 dark:border-slate-800 lg:w-72 lg:border-b-0 lg:border-r">
            {paths.map((p, i) => (
              <AccessPathCard
                key={p.id}
                path={p}
                selected={selectedIdx === i}
                onClick={() => setSelectedIdx(selectedIdx === i ? null : i)}
              />
            ))}
          </div>
          <div className="min-w-0 flex-1">
            <AccessPathGraph paths={displayPaths} height={440} />
          </div>
        </div>
      </div>
    </section>
  );
}

function RelatedCard({ identity }: { identity: IdentityProfile }) {
  const { projectId } = useProjectContext();
  const identityQuery = encodeURIComponent(identity.display_name || identity.id);
  const idQuery = encodeURIComponent(identity.id);
  const links = [
    {
      label: "Recommendation",
      description: "Least-privilege role plan",
      to: `/projects/${projectId}/recommendations/${identity.id}`,
    },
    {
      label: "Drift alerts",
      description: "Alerts filtered to this identity",
      to: `/projects/${projectId}/drift?search=${identityQuery}`,
    },
    {
      label: "Best-practice findings",
      description: "Configuration issues and remediation",
      to: `/projects/${projectId}/best-practices?identity=${idQuery}`,
    },
    {
      label: "Access paths",
      description: "Privilege escalation graph",
      to: `/projects/${projectId}/access-paths?identity=${idQuery}`,
    },
    {
      label: "PIM sessions",
      description: "Privileged activation history",
      to: `/projects/${projectId}/pim-sessions?identity=${idQuery}`,
    },
  ];

  return (
    <div className="card p-5">
      <h2 className="section-title">Related</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Jump to connected analysis for this identity.
      </p>
      <div className="mt-4 space-y-1">
        {links.map((link) => (
          <Link
            key={link.label}
            to={link.to}
            className="group flex items-center justify-between rounded-xl px-3 py-2.5 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/60"
          >
            <span>
              <span className="block text-sm font-medium text-slate-900 group-hover:text-brand-600 dark:text-white dark:group-hover:text-brand-400">
                {link.label}
              </span>
              <span className="mt-0.5 block text-xs text-slate-500 dark:text-slate-400">
                {link.description}
              </span>
            </span>
            <svg className="h-4 w-4 shrink-0 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-500 dark:text-slate-600 dark:group-hover:text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function IdentityDetail({ identity }: IdentityDetailProps) {
  const typeStyle = TYPE_COLORS[identity.identity_type];
  const risk = riskTone(identity.risk_score);

  return (
    <div className="space-y-6">
      <div className="card-glass relative overflow-hidden p-6">
        <div className="absolute inset-x-0 top-0 h-1 bg-brand-gradient" />
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 gap-4">
            <div className={clsx("flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-xl font-bold ring-1", typeStyle.avatar)}>
              {getInitials(identity.display_name)}
            </div>
            <div className="min-w-0">
              <p className="eyebrow">Identity Profile</p>
              <div className="mt-1 flex flex-wrap items-center gap-3">
                <h1 className="page-title truncate">{identity.display_name}</h1>
                <span className={clsx("badge", typeStyle.badge)}>
                  <span className={clsx("h-1.5 w-1.5 rounded-full", typeStyle.dot)} />
                  {identity.identity_type}
                </span>
              </div>
              <p className="page-subtitle">
                Roles, actions, privileged sessions, and escalation paths for this identity.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="chip max-w-full">
                  Object ID
                  <span className="truncate font-mono text-[11px] text-slate-500 dark:text-slate-400">
                    {identity.object_id}
                  </span>
                </span>
                {identity.upn && (
                  <span className="chip max-w-full">
                    UPN
                    <span className="truncate text-slate-500 dark:text-slate-400">
                      {identity.upn}
                    </span>
                  </span>
                )}
                {identity.app_id && (
                  <span className="chip max-w-full">
                    App ID
                    <span className="truncate font-mono text-[11px] text-slate-500 dark:text-slate-400">
                      {identity.app_id}
                    </span>
                  </span>
                )}
              </div>
            </div>
          </div>

          <RiskScoreRing score={identity.risk_score} />
        </div>
      </div>

      <MotionStagger className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <MotionItem>
          <StatCard
            label="Risk Score"
            value={clampScore(identity.risk_score)}
            color={risk.text}
            animated
          />
        </MotionItem>
        <MotionItem>
          <StatCard label="Total Actions" value={identity.action_count} animated />
        </MotionItem>
        <MotionItem>
          <StatCard label="Roles" value={identity.current_roles.length} animated />
        </MotionItem>
        <MotionItem>
          <StatCard label="First Seen" value={formatRelativeTime(identity.first_seen)} />
        </MotionItem>
        <MotionItem>
          <StatCard label="Last Seen" value={formatRelativeTime(identity.last_seen)} />
        </MotionItem>
      </MotionStagger>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <MotionStagger className="space-y-6">
          <MotionItem>
            <section>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="section-title">Current Roles</h2>
                <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  <AnimatedNumber value={identity.current_roles.length} />
                </span>
              </div>
              <div className="card overflow-hidden">
                <CurrentRolesTable roles={identity.current_roles} />
              </div>
            </section>
          </MotionItem>

          <MotionItem>
            <AccessPathsSection identityId={identity.id} />
          </MotionItem>

          <MotionItem>
            <section>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="section-title">PIM Sessions</h2>
                <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  Privileged activations
                </span>
              </div>
              <div className="card overflow-hidden">
                <PimSessionsTab identityId={identity.id} />
              </div>
            </section>
          </MotionItem>

          <MotionItem>
            <section>
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="section-title">Observed Actions</h2>
                <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  <AnimatedNumber value={identity.observed_actions.length} />
                  unique
                </span>
              </div>
              <div className="card overflow-hidden">
                <ObservedActionsTable actions={identity.observed_actions} />
              </div>
            </section>
          </MotionItem>

          <MotionItem>
            <section>
              <h2 className="section-title mb-3">Action Timeline</h2>
              <ActionTimeline identityId={identity.id} />
            </section>
          </MotionItem>
        </MotionStagger>

        <MotionItem className="xl:sticky xl:top-6 xl:self-start">
          <RelatedCard identity={identity} />
        </MotionItem>
      </div>
    </div>
  );
}
