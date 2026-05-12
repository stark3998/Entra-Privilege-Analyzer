// frontend/src/components/dashboard/TopRiskyIdentities.tsx
import { Link } from "react-router-dom";
import clsx from "clsx";

interface RiskyIdentity {
  id: string;
  display_name: string;
  identity_type: string;
  risk_score: number;
}

interface TopRiskyIdentitiesProps {
  /** Top identities ordered by risk score descending. */
  identities: RiskyIdentity[];
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  User: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  ServicePrincipal: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  ManagedIdentity: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  Group: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

function riskBarColor(score: number): string {
  if (score > 70) return "bg-red-500";
  if (score > 40) return "bg-amber-500";
  return "bg-emerald-500";
}

/**
 * Table showing the top 10 identities by risk score.
 * Rows are clickable and navigate to the identity detail page.
 *
 * Usage:
 * ```tsx
 * <TopRiskyIdentities identities={summary.top_risky_identities} />
 * ```
 */
export function TopRiskyIdentities({ identities }: TopRiskyIdentitiesProps) {
  if (identities.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Top Risky Identities
        </h3>
        <p className="mt-4 text-center text-sm text-slate-400 dark:text-slate-500">
          No risky identities found
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-300">
        Top Risky Identities
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700">
              <th className="pb-2 pr-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400">
                #
              </th>
              <th className="pb-2 pr-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400">
                Name
              </th>
              <th className="pb-2 pr-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400">
                Type
              </th>
              <th className="pb-2 text-left text-xs font-medium text-slate-500 dark:text-slate-400">
                Risk Score
              </th>
            </tr>
          </thead>
          <tbody>
            {identities.map((identity, idx) => (
              <tr key={identity.id} className="group border-b border-slate-100 last:border-0 dark:border-slate-800">
                <td className="py-2.5 pr-3 tabular-nums text-slate-400 dark:text-slate-500">
                  {idx + 1}
                </td>
                <td className="py-2.5 pr-3">
                  <Link
                    to={`/identities/${identity.id}`}
                    className="font-medium text-slate-900 group-hover:text-brand-600 dark:text-white dark:group-hover:text-brand-400"
                  >
                    {identity.display_name}
                  </Link>
                </td>
                <td className="py-2.5 pr-3">
                  <span
                    className={clsx(
                      "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                      TYPE_BADGE_COLORS[identity.identity_type] ?? "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                    )}
                  >
                    {identity.identity_type}
                  </span>
                </td>
                <td className="py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div
                        className={clsx("h-full rounded-full", riskBarColor(identity.risk_score))}
                        style={{ width: `${identity.risk_score}%` }}
                      />
                    </div>
                    <span className="text-xs font-medium tabular-nums text-slate-700 dark:text-slate-300">
                      {identity.risk_score}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
