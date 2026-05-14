import { Link } from "react-router-dom";
import clsx from "clsx";

interface ActiveIdentity {
  identity_id: string;
  display_name: string;
  identity_type: string;
  count: number;
}

interface MostActiveIdentitiesProps {
  identities: ActiveIdentity[];
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  User: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  ServicePrincipal:
    "bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300",
  ManagedIdentity:
    "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  Group:
    "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
};

export function MostActiveIdentities({
  identities,
}: MostActiveIdentitiesProps) {
  if (identities.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-400 dark:text-slate-500">
        No activity data
      </p>
    );
  }

  const maxCount = Math.max(1, ...identities.map((i) => i.count));

  return (
    <div className="space-y-1.5">
      {identities.map((identity, idx) => (
        <Link
          key={identity.identity_id}
          to={`../identities/${identity.identity_id}`}
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
                TYPE_BADGE_COLORS[identity.identity_type] ??
                  "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
              )}
            >
              {identity.identity_type}
            </span>
          </div>

          <div className="flex flex-shrink-0 items-center gap-2">
            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-indigo-500 transition-all"
                style={{ width: `${(identity.count / maxCount) * 100}%` }}
              />
            </div>
            <span className="w-10 text-right text-xs font-bold tabular-nums text-slate-700 dark:text-slate-300">
              {identity.count.toLocaleString()}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}
