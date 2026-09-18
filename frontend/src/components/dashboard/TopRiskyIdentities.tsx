import { Link } from "react-router-dom";
import clsx from "clsx";
import { Tooltip } from "@/components/common/Tooltip";
import { useProjectContext } from "@/store/projectContext";

interface RiskyIdentity {
  id: string;
  display_name: string;
  identity_type: string;
  risk_score: number;
}

interface TopRiskyIdentitiesProps {
  identities: RiskyIdentity[];
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  User: "bg-brand-50 text-brand-700 dark:bg-brand-950/40 dark:text-brand-300",
  ServicePrincipal: "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300",
  ManagedIdentity: "bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300",
  Group: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
};

function riskBarColor(score: number): string {
  if (score > 70) return "bg-red-500";
  if (score > 40) return "bg-amber-500";
  return "bg-emerald-500";
}

export function TopRiskyIdentities({ identities }: TopRiskyIdentitiesProps) {
  const { projectId } = useProjectContext();
  return (
    <div className="card p-6">
      <div className="mb-4 flex items-center gap-2">
        <h3 className="section-title">Top Risky Identities</h3>
        <Tooltip content="Identities ranked by composite risk score (highest first)">
          <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </Tooltip>
      </div>

      {identities.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
          No risky identities found
        </p>
      ) : (
        <div className="space-y-1">
          {identities.map((identity, idx) => (
            <Link
              key={identity.id}
              to={`/projects/${projectId}/identities/${identity.id}`}
              className="group flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all hover:bg-slate-50 dark:hover:bg-slate-800/60"
            >
              <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold tabular-nums text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {idx + 1}
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-900 group-hover:text-brand-600 dark:text-white dark:group-hover:text-brand-400">
                  {identity.display_name}
                </p>
                <span
                  className={clsx(
                    "mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-medium",
                    TYPE_BADGE_COLORS[identity.identity_type] ?? "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                  )}
                >
                  {identity.identity_type}
                </span>
              </div>

              <div className="flex flex-shrink-0 items-center gap-2">
                <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className={clsx("h-full rounded-full transition-all", riskBarColor(identity.risk_score))}
                    style={{ width: `${identity.risk_score}%` }}
                  />
                </div>
                <span className="w-7 text-right text-xs font-bold tabular-nums text-slate-700 dark:text-slate-300">
                  {identity.risk_score}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
