// frontend/src/components/identities/IdentityTable.tsx
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { DataTable, type Column } from "@/components/common/DataTable";
import { AnimatedNumber } from "@/components/common/AnimatedNumber";
import { useProjectContext } from "@/store/projectContext";
import { formatRelativeTime } from "@/utils/formatRelativeTime";
import type { IdentityProfile, IdentityType } from "@/api/types";

interface IdentityTableProps {
  data: IdentityProfile[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  isLoading?: boolean;
}

/** Color map for identity type badges. */
const TYPE_COLORS: Record<IdentityType, { bg: string; dot: string }> = {
  User: { bg: "bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300", dot: "bg-brand-500" },
  ServicePrincipal: { bg: "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300", dot: "bg-violet-500" },
  ManagedIdentity: { bg: "bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300", dot: "bg-teal-500" },
  Group: { bg: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300", dot: "bg-amber-500" },
};

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "ID";
}

function RiskBadge({ score }: { score: number }) {
  const barColor = score > 70 ? "bg-red-500" : score > 40 ? "bg-amber-500" : "bg-emerald-500";
  const badgeColor = score > 70
    ? "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
    : score > 40
      ? "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";

  return (
    <div className="flex items-center gap-2.5">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={clsx("h-full rounded-full transition-all", barColor)}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className={clsx("badge tabular-nums", badgeColor)}>
        <AnimatedNumber value={score} />
      </span>
    </div>
  );
}

const columns: Column<IdentityProfile>[] = [
  {
    key: "name",
    header: "Name",
    render: (item) => (
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-xs font-bold text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
          {getInitials(item.display_name)}
        </div>
        <div className="min-w-0">
          <p className="truncate font-medium text-slate-900 dark:text-white">
            {item.display_name}
          </p>
          {(item.upn || item.app_id) && (
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              {item.upn ?? item.app_id}
            </p>
          )}
        </div>
      </div>
    ),
  },
  {
    key: "type",
    header: "Type",
    render: (item) => {
      const c = TYPE_COLORS[item.identity_type];
      return (
        <span className={clsx("badge", c.bg)}>
          <span className={clsx("h-1.5 w-1.5 rounded-full", c.dot)} />
          {item.identity_type}
        </span>
      );
    },
  },
  {
    key: "roles",
    header: "Roles",
    render: (item) =>
      item.current_roles.length > 0 ? (
        <span className="chip tabular-nums">
          <AnimatedNumber value={item.current_roles.length} />
        </span>
      ) : (
        <span className="text-sm text-slate-400 dark:text-slate-500">
          No roles
        </span>
      ),
  },
  {
    key: "actions",
    header: "Actions",
    render: (item) => (
      <span className="text-sm font-medium tabular-nums text-slate-700 dark:text-slate-300">
        <AnimatedNumber value={item.action_count} />
      </span>
    ),
  },
  {
    key: "risk",
    header: "Risk Score",
    render: (item) => <RiskBadge score={item.risk_score} />,
  },
  {
    key: "lastActive",
    header: "Last Active",
    render: (item) => (
      <span className="text-sm text-slate-500 dark:text-slate-400">
        {formatRelativeTime(item.last_seen)}
      </span>
    ),
  },
];

/**
 * Identity list table built on the reusable DataTable.
 * Clicking a row navigates to the identity detail page.
 */
export function IdentityTable({
  data,
  total,
  page,
  pageSize,
  onPageChange,
  isLoading,
}: IdentityTableProps) {
  const navigate = useNavigate();
  const { projectId } = useProjectContext();

  return (
    <DataTable<IdentityProfile>
      columns={columns}
      data={data}
      total={total}
      page={page}
      pageSize={pageSize}
      onPageChange={onPageChange}
      onRowClick={(item) => navigate(`/projects/${projectId}/identities/${item.id}`)}
      isLoading={isLoading}
      emptyMessage="No identities found"
    />
  );
}
