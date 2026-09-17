import type { EvidenceCoverageSummary } from "@/api/types";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { formatPercent, formatDateTime } from "@/utils/governanceFormatting";

export function EvidenceCoverageCard({
  summary,
}: {
  summary: EvidenceCoverageSummary;
}) {
  const averageCompleteness =
    summary.sources.length > 0
      ? summary.sources.reduce((sum, source) => sum + source.completeness, 0) /
        summary.sources.length
      : 0;
  const averageConfidence =
    summary.sources.length > 0
      ? summary.sources.reduce((sum, source) => sum + source.confidence, 0) /
        summary.sources.length
      : 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <GovernanceMetricCard
          label="Sources"
          value={summary.sources.length}
          caption={`Tenant ${summary.tenant_id}`}
          tone="brand"
        />
        <GovernanceMetricCard
          label="Complete"
          value={summary.complete ? "Yes" : "No"}
          caption="All sources at 90% completeness or better"
          tone={summary.complete ? "emerald" : "amber"}
        />
        <GovernanceMetricCard
          label="Avg completeness"
          value={formatPercent(averageCompleteness * 100, 0)}
          tone="brand"
        />
        <GovernanceMetricCard
          label="Avg confidence"
          value={formatPercent(averageConfidence * 100, 0)}
          tone="slate"
        />
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="section-title">Evidence source health</h2>
            <p className="page-subtitle mt-1">
              Raw data-quality status returned by the evidence health endpoint
            </p>
          </div>
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
            {summary.sources.length} source{summary.sources.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="mt-5 space-y-4">
          {summary.sources.map((source) => (
            <div key={source.id} className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-800/40">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-slate-900 dark:text-white">{source.source}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Assessed {formatDateTime(source.assessed_at)}
                  </p>
                </div>
                <div className="text-right text-sm text-slate-600 dark:text-slate-300">
                  <p>Completeness {formatPercent(source.completeness * 100, 0)}</p>
                  <p>Confidence {formatPercent(source.confidence * 100, 0)}</p>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 text-xs text-slate-500 dark:text-slate-400 md:grid-cols-2">
                <p>Coverage start: {formatDateTime(source.coverage_start)}</p>
                <p>Coverage end: {formatDateTime(source.coverage_end)}</p>
              </div>
              {source.gaps.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {source.gaps.map((gap) => (
                    <span
                      key={gap}
                      className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
                    >
                      {gap}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
