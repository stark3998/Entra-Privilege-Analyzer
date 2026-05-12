// frontend/src/components/common/DataTable.tsx
import clsx from "clsx";
import { EmptyState } from "./EmptyState";

export interface Column<T> {
  /** Unique key for the column, used as the React key. */
  key: string;
  /** Text displayed in the table header. */
  header: string;
  /** Render function for each cell in this column. */
  render: (item: T) => React.ReactNode;
  /** Whether clicking the header should sort (not yet wired). */
  sortable?: boolean;
  /** Additional CSS classes applied to both th and td. */
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onRowClick?: (item: T) => void;
  isLoading?: boolean;
  emptyMessage?: string;
}

/** Number of skeleton rows shown while loading. */
const SKELETON_ROWS = 5;

/**
 * Reusable paginated data table with loading skeleton,
 * empty state, row click support, and dark mode.
 */
export function DataTable<T>({
  columns,
  data,
  total,
  page,
  pageSize,
  onPageChange,
  onRowClick,
  isLoading,
  emptyMessage = "No data found",
}: DataTableProps<T>) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
      {/* Horizontal scroll wrapper for mobile */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
          <thead className="bg-slate-50 dark:bg-slate-800/50">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={clsx(
                    "px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400",
                    col.className,
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 bg-white dark:divide-slate-800 dark:bg-slate-900">
            {isLoading
              ? Array.from({ length: SKELETON_ROWS }).map((_, rowIdx) => (
                  <tr key={`skeleton-${rowIdx}`}>
                    {columns.map((col) => (
                      <td key={col.key} className={clsx("px-4 py-3", col.className)}>
                        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
                      </td>
                    ))}
                  </tr>
                ))
              : data.map((item, rowIdx) => (
                  <tr
                    key={rowIdx}
                    onClick={() => onRowClick?.(item)}
                    className={clsx(
                      "transition-colors",
                      onRowClick &&
                        "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60",
                    )}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={clsx(
                          "whitespace-nowrap px-4 py-3 text-sm text-slate-700 dark:text-slate-300",
                          col.className,
                        )}
                      >
                        {col.render(item)}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {/* Empty state — shown when not loading and no data */}
      {!isLoading && data.length === 0 && (
        <div className="p-6">
          <EmptyState
            title={emptyMessage}
            icon={
              <svg
                className="h-10 w-10"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                />
              </svg>
            }
          />
        </div>
      )}

      {/* Pagination */}
      {total > 0 && (
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/50">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Showing {startItem}&ndash;{endItem} of {total}
          </p>

          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className={clsx(
                "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                page <= 1
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
              )}
            >
              Prev
            </button>

            {buildPageNumbers(page, totalPages).map((p, idx) =>
              p === null ? (
                <span
                  key={`ellipsis-${idx}`}
                  className="px-1 text-xs text-slate-400 dark:text-slate-500"
                >
                  ...
                </span>
              ) : (
                <button
                  key={p}
                  onClick={() => onPageChange(p)}
                  className={clsx(
                    "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                    p === page
                      ? "bg-brand-600 text-white dark:bg-brand-500"
                      : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
                  )}
                >
                  {p}
                </button>
              ),
            )}

            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className={clsx(
                "rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                page >= totalPages
                  ? "cursor-not-allowed text-slate-300 dark:text-slate-600"
                  : "text-slate-600 hover:bg-slate-200 dark:text-slate-300 dark:hover:bg-slate-700",
              )}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Build an array of page numbers (with null for ellipsis gaps)
 * to display in the pagination controls.
 */
function buildPageNumbers(
  current: number,
  total: number,
): (number | null)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | null)[] = [1];

  if (current > 3) pages.push(null);

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) pages.push(null);

  pages.push(total);

  return pages;
}
