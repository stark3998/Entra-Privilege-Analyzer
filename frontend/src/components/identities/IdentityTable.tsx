// frontend/src/components/identities/IdentityTable.tsx
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { DataTable, type Column } from "@/components/common/DataTable";
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
  User: { bg: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300", dot: "bg-blue-500" },
  ServicePrincipal: { bg: "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300", dot: "bg-purple-500" },
  ManagedIdentity: { bg: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300", dot: "bg-emerald-500" },
  Group: { bg: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300", dot: "bg-amber-500" },
};

function RiskBadge({ score }: { score: number }) {
  const barColor = score > 70 ? "bg-red-500" : score > 40 ? "bg-amber-500" : "bg-emerald-500";
  const badgeColor = score > 70
    ? "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
    : score > 40
      ? "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={clsx("h-full rounded-full transition-all", barColor)}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className={clsx("inline-flex rounded-md px-1.5 py-0.5 text-xs font-semibold", badgeColor)}>
        {score}
      </span>
    </div>
  );
}

const columns: Column<IdentityProfile>[] = [
  {
    key: "name",
    header: "Name",
    render: (item) => (
      <div>
        <p className="font-medium text-slate-900 dark:text-white">
          {item.display_name}
        </p>
        {(item.upn || item.app_id) && (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {item.upn ?? item.app_id}
          </p>
        )}
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
        <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
          {item.current_roles.length}
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
      <span className="text-sm tabular-nums text-slate-700 dark:text-slate-300">
        {item.action_count.toLocaleString()}
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

  return (
    <DataTable<IdentityProfile>
      columns={columns}
      data={data}
      total={total}
      page={page}
      pageSize={pageSize}
      onPageChange={onPageChange}
      onRowClick={(item) => navigate(`/identities/${item.id}`)}
      isLoading={isLoading}
      emptyMessage="No identities found"
    />
  );
}
