import clsx from "clsx";
import type { GovernanceConnector } from "@/api/types";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

export function ConnectorCard({
  connector,
  selected,
  onSelect,
}: {
  connector: GovernanceConnector;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={clsx(
        "card w-full p-4 text-left transition-all",
        selected
          ? "border-brand-300 ring-2 ring-brand-100 dark:border-brand-700 dark:ring-brand-900/40"
          : "hover:border-slate-300 dark:hover:border-slate-600",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
          {connector.connector_type}
        </span>
        <span
          className={`badge ${
            connector.enabled
              ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
              : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
          }`}
        >
          {connector.enabled ? "Enabled" : "Disabled"}
        </span>
      </div>
      <div className="mt-3">
        <h3 className="break-all text-sm font-semibold text-slate-900 dark:text-white">
          {connector.endpoint}
        </h3>
        <p className="mt-1 text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {connector.id}
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
        <span>Updated {formatRelativeTime(connector.updated_at)}</span>
        <span>-</span>
        <span>{Object.keys(connector.settings).length} setting keys</span>
      </div>
    </button>
  );
}
