import { Link } from "react-router-dom";
import type { EvidenceRecord } from "@/api/types";
import { DataTable, type Column } from "@/components/common/DataTable";
import { CoverageBadge } from "@/components/governance/GovernanceBadges";
import { formatDateTime } from "@/utils/governanceFormatting";

interface EvidenceExplorerTableProps {
  items: EvidenceRecord[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  projectId: string;
  isLoading?: boolean;
}

const columns = (projectId: string): Column<EvidenceRecord>[] => [
  {
    key: "title",
    header: "Evidence",
    className: "min-w-[18rem] whitespace-normal",
    render: (item) => (
      <div>
        <p className="font-medium text-slate-900 dark:text-white">{item.title}</p>
        <p className="mt-1 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
          {item.summary}
        </p>
        {item.linked_workflow_id && (
          <Link
            to={`/projects/${projectId}/workflows/${item.linked_workflow_id}`}
            className="mt-2 inline-flex text-xs font-semibold text-brand-600 hover:text-brand-700 dark:text-brand-400"
            onClick={(event) => event.stopPropagation()}
          >
            View workflow
          </Link>
        )}
      </div>
    ),
  },
  {
    key: "coverage",
    header: "Coverage",
    render: (item) => <CoverageBadge status={item.coverage_status} />,
  },
  {
    key: "family",
    header: "Control Family",
    render: (item) => (
      <div>
        <p>{item.control_family}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">{item.evidence_type}</p>
      </div>
    ),
  },
  {
    key: "source",
    header: "Source",
    render: (item) => (
      <div>
        <p>{item.source}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {item.owners.length > 0 ? item.owners.join(", ") : "No owners"}
        </p>
      </div>
    ),
  },
  {
    key: "freshness",
    header: "Freshness",
    render: (item) => (
      <div>
        <p>Collected {formatDateTime(item.collected_at)}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Expires {formatDateTime(item.expires_at)}
        </p>
      </div>
    ),
  },
];

export function EvidenceExplorerTable({
  items,
  total,
  page,
  pageSize,
  onPageChange,
  projectId,
  isLoading,
}: EvidenceExplorerTableProps) {
  return (
    <DataTable
      columns={columns(projectId)}
      data={items}
      total={total}
      page={page}
      pageSize={pageSize}
      onPageChange={onPageChange}
      isLoading={isLoading}
      emptyMessage="No evidence matches the current filters"
    />
  );
}
