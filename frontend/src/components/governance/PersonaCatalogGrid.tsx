import clsx from "clsx";
import type { PersonaCatalogEntry, PersonaStatus } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { formatDateTime } from "@/utils/governanceFormatting";

const STATUS_CLASSES: Record<PersonaStatus, string> = {
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  evaluating: "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  approved: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
  published: "bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300",
  superseded: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  retired: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};

export function PersonaCatalogGrid({
  personas,
}: {
  personas: PersonaCatalogEntry[];
}) {
  if (personas.length === 0) {
    return (
      <EmptyState
        title="No personas published"
        description="Governance personas will appear here after the backend persists persona records."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
      {personas.map((persona) => (
        <div key={persona.id} className="card p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={clsx("badge", STATUS_CLASSES[persona.status])}>
              {persona.status}
            </span>
            <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              Version {persona.version}
            </span>
            {persona.builtin_role_name && (
              <span className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
                {persona.builtin_role_name}
              </span>
            )}
          </div>

          <div className="mt-3">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              {persona.name}
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              {persona.id}
            </p>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Members</p>
              <p className="mt-1 font-medium text-slate-900 dark:text-white">
                {persona.member_identity_ids.length}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Match score</p>
              <p className="mt-1 font-medium text-slate-900 dark:text-white">
                {(persona.match_score * 100).toFixed(0)}%
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Updated</p>
              <p className="mt-1 font-medium text-slate-900 dark:text-white">
                {formatDateTime(persona.updated_at)}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Approved by</p>
              <p className="mt-1 font-medium text-slate-900 dark:text-white">
                {persona.approved_by ?? "Not approved"}
              </p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Common permissions
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {persona.common_permissions.length > 0 ? (
                  persona.common_permissions.map((permission) => (
                    <span
                      key={permission}
                      className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                    >
                      {permission}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-slate-500 dark:text-slate-400">None recorded</span>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Justified rare permissions
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {persona.justified_rare_permissions.length > 0 ? (
                  persona.justified_rare_permissions.map((permission) => (
                    <span
                      key={permission}
                      className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-900/20 dark:text-amber-300"
                    >
                      {permission}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-slate-500 dark:text-slate-400">None recorded</span>
                )}
              </div>
            </div>
          </div>

          {(persona.escalation_findings.length > 0 || persona.sod_findings.length > 0) && (
            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Escalation findings
                </p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  {persona.escalation_findings.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-red-500" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  SoD findings
                </p>
                <ul className="mt-2 space-y-1 text-sm text-slate-700 dark:text-slate-300">
                  {persona.sod_findings.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-1 h-1.5 w-1.5 rounded-full bg-orange-500" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {persona.custom_role_definition && (
            <div className="mt-4">
              <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Custom role definition
              </p>
              <div className="mt-2">
                <JsonViewer content={JSON.stringify(persona.custom_role_definition, null, 2)} language="json" maxHeight="max-h-64" />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
