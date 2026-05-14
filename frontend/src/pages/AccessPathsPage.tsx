import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAccessPaths } from "@/api/hooks";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { AccessPathSummaryCard } from "@/components/access-paths/AccessPathSummaryCard";

type RiskFilter = "" | "critical" | "high" | "medium";

export function AccessPathsPage() {
  const navigate = useNavigate();
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("");
  const [page, setPage] = useState(1);
  const size = 20;

  const { data, isLoading } = useAccessPaths({
    minRisk: riskFilter || undefined,
    page,
    size,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / size);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
          Privilege Escalation Paths
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Indirect privilege escalation routes through app ownership, group membership, and SP permissions
        </p>
      </div>

      <AccessPathSummaryCard />

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-700">
          <div className="flex items-center gap-2">
            <label htmlFor="risk-filter" className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Min Risk:
            </label>
            <select
              id="risk-filter"
              value={riskFilter}
              onChange={(e) => { setRiskFilter(e.target.value as RiskFilter); setPage(1); }}
              className="rounded border border-slate-300 bg-white px-2 py-1 text-xs dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
            >
              <option value="">All</option>
              <option value="critical">Critical</option>
              <option value="high">High+</option>
              <option value="medium">Medium+</option>
            </select>
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {total} {total === 1 ? "identity" : "identities"} with paths
          </span>
        </div>

        {isLoading ? (
          <div className="animate-pulse p-6">
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 rounded bg-slate-100 dark:bg-slate-700" />
              ))}
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-sm text-slate-400 dark:text-slate-500">
            No privilege escalation paths found
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-semibold uppercase text-slate-500 dark:border-slate-700 dark:text-slate-400">
                <th className="px-4 py-3">Identity</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-center">Critical</th>
                <th className="px-4 py-3 text-center">High</th>
                <th className="px-4 py-3 text-center">Medium</th>
                <th className="px-4 py-3 text-center">Total</th>
                <th className="px-4 py-3">Highest Risk</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => navigate(`../identities/${item.identity_id}`)}
                  className="cursor-pointer border-b border-slate-100 transition-colors hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50"
                >
                  <td className="px-4 py-3 font-medium text-slate-900 dark:text-white">
                    {item.identity_display_name}
                  </td>
                  <td className="px-4 py-3 text-slate-500 dark:text-slate-400">
                    {item.identity_type}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {item.critical_paths > 0 ? (
                      <span className="font-bold text-red-600 dark:text-red-400">{item.critical_paths}</span>
                    ) : (
                      <span className="text-slate-300 dark:text-slate-600">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {item.high_paths > 0 ? (
                      <span className="font-bold text-orange-600 dark:text-orange-400">{item.high_paths}</span>
                    ) : (
                      <span className="text-slate-300 dark:text-slate-600">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {item.medium_paths > 0 ? (
                      <span className="font-bold text-amber-600 dark:text-amber-400">{item.medium_paths}</span>
                    ) : (
                      <span className="text-slate-300 dark:text-slate-600">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center font-semibold text-slate-900 dark:text-white">
                    {item.total_paths}
                  </td>
                  <td className="px-4 py-3">
                    {item.highest_risk !== "none" && (
                      <SeverityBadge severity={item.highest_risk as "critical" | "high" | "medium"} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 dark:border-slate-700">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 disabled:opacity-40 dark:border-slate-600 dark:text-slate-400"
            >
              Previous
            </button>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 disabled:opacity-40 dark:border-slate-600 dark:text-slate-400"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
