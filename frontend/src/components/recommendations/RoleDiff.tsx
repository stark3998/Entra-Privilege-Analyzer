// frontend/src/components/recommendations/RoleDiff.tsx
import { useState } from "react";
import clsx from "clsx";
import type {
  CurrentRole,
  BuiltInRoleMatch,
  CustomRoleDefinition,
} from "@/api/types";

interface RoleDiffProps {
  currentRoles: CurrentRole[];
  bestBuiltinMatch: BuiltInRoleMatch | null;
  alternativeBuiltins: BuiltInRoleMatch[];
  customRole: CustomRoleDefinition;
}

/** Color map for match score badges. */
function matchScoreColor(score: number): string {
  if (score > 80)
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400";
  if (score > 50)
    return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400";
  return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400";
}

/** Color map for assignment type badges. */
const ASSIGNMENT_COLORS: Record<string, string> = {
  direct:
    "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  group:
    "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  pim:
    "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
};

function BuiltInMatchCard({ match }: { match: BuiltInRoleMatch }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800/60">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900 dark:text-white">
            {match.role_name}
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Scope: {match.scope} &middot; {match.permissions_matched}/
            {match.permissions_total} permissions matched
          </p>
          {match.excess_permissions.length > 0 && (
            <p className="mt-1 text-xs text-red-600 dark:text-red-400">
              {match.excess_permissions.length} excess permission
              {match.excess_permissions.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <span
          className={clsx(
            "inline-flex flex-shrink-0 rounded px-2 py-0.5 text-xs font-bold",
            matchScoreColor(match.match_score),
          )}
        >
          {match.match_score}%
        </span>
      </div>
    </div>
  );
}

/**
 * Side-by-side comparison of current roles (left) vs. recommended roles (right).
 * Shows the best built-in match with score badge and collapsible alternatives.
 *
 * Usage:
 * ```tsx
 * <RoleDiff
 *   currentRoles={rec.current_roles}
 *   bestBuiltinMatch={rec.best_builtin_match}
 *   alternativeBuiltins={rec.alternative_builtins}
 *   customRole={rec.custom_role}
 * />
 * ```
 */
export function RoleDiff({
  currentRoles,
  bestBuiltinMatch,
  alternativeBuiltins,
  customRole,
}: RoleDiffProps) {
  const [showAlternatives, setShowAlternatives] = useState(false);

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {/* Left: Current Roles */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Current Roles
        </h3>
        <div className="space-y-2">
          {currentRoles.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-400 dark:text-slate-500">
              No roles assigned
            </p>
          ) : (
            currentRoles.map((role) => (
              <div
                key={role.role_id}
                className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-800/60"
              >
                <p className="text-sm font-medium text-slate-900 dark:text-white">
                  {role.role_name}
                </p>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span
                    className="max-w-[200px] truncate"
                    title={role.scope}
                  >
                    {role.scope}
                  </span>
                  <span
                    className={clsx(
                      "inline-flex rounded px-1.5 py-0.5 text-xs font-medium",
                      ASSIGNMENT_COLORS[role.assignment_type.toLowerCase()] ??
                        "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300",
                    )}
                  >
                    {role.assignment_type}
                  </span>
                  {role.is_permanent && (
                    <span className="text-amber-600 dark:text-amber-400">
                      Permanent
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right: Recommended */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Recommended
        </h3>
        <div className="space-y-3">
          {/* Arrow indicator */}
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 7l5 5m0 0l-5 5m5-5H6"
              />
            </svg>
            <span>Replace with least-privilege role</span>
          </div>

          {/* Best built-in match */}
          {bestBuiltinMatch ? (
            <>
              <div className="relative">
                <span className="absolute -top-2 left-3 rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold uppercase text-white dark:bg-emerald-500">
                  Best Match
                </span>
                <BuiltInMatchCard match={bestBuiltinMatch} />
              </div>
            </>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400">
              No built-in role matches found. A custom role is recommended.
            </p>
          )}

          {/* Custom role fallback */}
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 dark:border-slate-600 dark:bg-slate-800/30">
            <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
              Custom Role Alternative
            </p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              {customRole.name} &mdash; {customRole.description}
            </p>
          </div>

          {/* Alternatives (collapsible) */}
          {alternativeBuiltins.length > 0 && (
            <div>
              <button
                onClick={() => setShowAlternatives(!showAlternatives)}
                className="flex items-center gap-1 text-xs font-medium text-brand-600 transition-colors hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                <svg
                  className={clsx(
                    "h-3.5 w-3.5 transition-transform",
                    showAlternatives && "rotate-90",
                  )}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
                {alternativeBuiltins.length} alternative built-in role
                {alternativeBuiltins.length !== 1 ? "s" : ""}
              </button>
              {showAlternatives && (
                <div className="mt-2 space-y-2">
                  {alternativeBuiltins.map((alt) => (
                    <BuiltInMatchCard key={alt.role_id} match={alt} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
