import { useEffect, useMemo, useState } from "react";
import { useAuthorizationReadiness, useGovernanceConnectors } from "@/api/hooks";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { ConnectorCard } from "@/components/governance/ConnectorCard";
import { GovernanceErrorState } from "@/components/governance/GovernanceFeedback";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { MotionItem, MotionStagger } from "@/components/common/motion";
import { formatDateTime, toTitleCase } from "@/utils/governanceFormatting";

export function ConnectorAdminPage() {
  const readinessQuery = useAuthorizationReadiness();
  const { data, isLoading, isError, error } = useGovernanceConnectors();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const connectors = data ?? [];

  useEffect(() => {
    if (!selectedId && connectors.length > 0) {
      setSelectedId(connectors[0].id);
      return;
    }
    if (selectedId && !connectors.some((connector) => connector.id === selectedId)) {
      setSelectedId(connectors[0]?.id ?? null);
    }
  }, [connectors, selectedId]);

  const selectedConnector = useMemo(
    () => connectors.find((connector) => connector.id === selectedId) ?? null,
    [connectors, selectedId],
  );

  if (isError) {
    return <GovernanceErrorState error={error} feature="connector inventory" />;
  }

  const enabledCount = connectors.filter((connector) => connector.enabled).length;
  const secretBackedCount = connectors.filter((connector) => connector.secret_reference).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Governance Integrations</p>
          <h1 className="page-title mt-1">Connector Administration</h1>
          <p className="page-subtitle">
            Read-only inspection of configured governance connectors using the backend-supported GET endpoint
          </p>
        </div>
      </div>

      <MotionStagger className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <MotionItem><GovernanceMetricCard label="Connectors" value={connectors.length} tone="brand" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="Enabled" value={enabledCount} tone="emerald" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="Secret-backed" value={secretBackedCount} tone="slate" /></MotionItem>
      </MotionStagger>

      {readinessQuery.isError && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-300">
          {readinessQuery.error instanceof Error
            ? readinessQuery.error.message
            : "Authorization readiness is unavailable."}
        </div>
      )}

      {readinessQuery.data && (
        <div
          className={`card p-4 text-sm ${
            readinessQuery.data.ready
              ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20"
              : "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20"
          }`}
        >
          <p className="font-semibold text-slate-900 dark:text-white">Authorization readiness</p>
          <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
            <p>Mode: {toTitleCase(readinessQuery.data.mode)}</p>
            <p>Collection: {readinessQuery.data.collection_ready ? "Ready" : "Not ready"}</p>
            <p>Mutation: {readinessQuery.data.mutation_ready ? "Ready" : "Not ready"}</p>
            <p>Delegated: {readinessQuery.data.delegated_ready ? "Ready" : "Not ready"}</p>
          </div>
          {(readinessQuery.data.missing.length > 0 || readinessQuery.data.warnings.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {readinessQuery.data.missing.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-white/80 px-2.5 py-1 text-xs font-medium text-red-700 dark:bg-slate-900/50 dark:text-red-300"
                >
                  Missing: {item}
                </span>
              ))}
              {readinessQuery.data.warnings.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-white/80 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-slate-900/50 dark:text-amber-300"
                >
                  Warning: {item}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr,1.25fr]">
        <div className="space-y-3">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="card p-4">
                <div className="skeleton h-4 w-1/3" />
                <div className="skeleton mt-3 h-10" />
              </div>
            ))
          ) : connectors.length === 0 ? (
            <EmptyState
              title="No connectors configured"
              description="Connector inventory will appear here after backend connector records are created."
            />
          ) : (
            <MotionStagger className="space-y-3">
              {connectors.map((connector) => (
                <MotionItem key={connector.id}>
                  <ConnectorCard
                    connector={connector}
                    selected={connector.id === selectedId}
                    onSelect={() => setSelectedId(connector.id)}
                  />
                </MotionItem>
              ))}
            </MotionStagger>
          )}
        </div>

        {selectedConnector ? (
          <div className="space-y-5">
            <div className="card p-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
                  {selectedConnector.connector_type}
                </span>
                <span
                  className={`badge ${
                    selectedConnector.enabled
                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                      : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {selectedConnector.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
              <h2 className="mt-3 break-all text-xl font-semibold text-slate-900 dark:text-white">
                {selectedConnector.endpoint}
              </h2>
              <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Created</p>
                  <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                    {formatDateTime(selectedConnector.created_at)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Updated</p>
                  <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                    {formatDateTime(selectedConnector.updated_at)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Secret reference</p>
                  <p className="mt-1 break-all text-sm font-medium text-slate-900 dark:text-white">
                    {selectedConnector.secret_reference ?? "Not configured"}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Setting keys</p>
                  <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                    {Object.keys(selectedConnector.settings).length}
                  </p>
                </div>
              </div>
            </div>

            <div className="card p-5">
              <h2 className="section-title">Connector settings</h2>
              <div className="mt-4">
                <JsonViewer content={JSON.stringify(selectedConnector.settings, null, 2)} language="json" maxHeight="max-h-80" />
              </div>
            </div>
          </div>
        ) : (
          <EmptyState
            title="Select a connector"
            description="Choose a connector to inspect its endpoint, secret reference, and settings payload."
          />
        )}
      </div>
    </div>
  );
}
