import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  useEvidenceCoverage,
  useIdentities,
  useIdentityEvidenceAccess,
} from "@/api/hooks";
import type { IdentityType } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { EvidenceCoverageCard } from "@/components/governance/EvidenceCoverageCard";
import { GovernanceErrorState } from "@/components/governance/GovernanceFeedback";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { useProjectContext } from "@/store/projectContext";
import { formatDateTime } from "@/utils/governanceFormatting";

const PAGE_SIZE = 12;

export function EvidenceExplorerPage() {
  const { projectId } = useProjectContext();
  const [search, setSearch] = useState("");
  const [identityType, setIdentityType] = useState<IdentityType | "">("");
  const [page, setPage] = useState(1);
  const [selectedIdentityId, setSelectedIdentityId] = useState<string | null>(null);

  const coverageQuery = useEvidenceCoverage();
  const identitiesQuery = useIdentities({
    search: search || undefined,
    type: identityType || undefined,
    page,
    size: PAGE_SIZE,
  });

  const identities = identitiesQuery.data?.items ?? [];

  useEffect(() => {
    if (!selectedIdentityId && identities.length > 0) {
      setSelectedIdentityId(identities[0].id);
      return;
    }
    if (selectedIdentityId && !identities.some((identity) => identity.id === selectedIdentityId)) {
      setSelectedIdentityId(identities[0]?.id ?? null);
    }
  }, [identities, selectedIdentityId]);

  const selectedIdentity = useMemo(
    () => identities.find((identity) => identity.id === selectedIdentityId) ?? null,
    [identities, selectedIdentityId],
  );
  const accessQuery = useIdentityEvidenceAccess(selectedIdentityId ?? "");

  if (coverageQuery.isError) {
    return <GovernanceErrorState error={coverageQuery.error} feature="evidence health" />;
  }

  if (identitiesQuery.isError) {
    return <GovernanceErrorState error={identitiesQuery.error} feature="project identities" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Evidence Explorer</h1>
          <p className="page-subtitle">
            Inspect raw evidence source health and identity access edges returned by governance evidence endpoints
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={identityType}
            onChange={(event) => {
              setIdentityType(event.target.value as IdentityType | "");
              setPage(1);
            }}
            className="input-base py-2"
            aria-label="Filter identity type"
          >
            <option value="">All identity types</option>
            <option value="User">User</option>
            <option value="ServicePrincipal">Service principal</option>
            <option value="ManagedIdentity">Managed identity</option>
            <option value="Group">Group</option>
          </select>
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="input-base min-w-72 py-2"
            placeholder="Search identities"
            aria-label="Search evidence explorer identities"
          />
        </div>
      </div>

      {coverageQuery.data && <EvidenceCoverageCard summary={coverageQuery.data} />}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr,1.25fr]">
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3 xl:grid-cols-1">
            <GovernanceMetricCard label="Loaded identities" value={identities.length} tone="brand" />
            <GovernanceMetricCard label="Total identities" value={identitiesQuery.data?.total ?? 0} tone="slate" />
            <GovernanceMetricCard
              label="Access edges"
              value={accessQuery.data?.items.length ?? 0}
              tone="emerald"
            />
          </div>

          {identitiesQuery.isLoading ? (
            Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="card animate-pulse p-4">
                <div className="h-4 w-1/3 rounded bg-slate-100 dark:bg-slate-800" />
                <div className="mt-3 h-10 rounded bg-slate-100 dark:bg-slate-800" />
              </div>
            ))
          ) : identities.length === 0 ? (
            <EmptyState
              title="No identities available"
              description="The evidence access view requires project identities to be present."
            />
          ) : (
            <div className="space-y-3">
              {identities.map((identity) => (
                <button
                  key={identity.id}
                  type="button"
                  onClick={() => setSelectedIdentityId(identity.id)}
                  className={`card w-full p-4 text-left transition-all ${
                    identity.id === selectedIdentityId
                      ? "border-brand-300 ring-2 ring-brand-100 dark:border-brand-700 dark:ring-brand-900/40"
                      : "hover:border-slate-300 dark:hover:border-slate-600"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      {identity.identity_type}
                    </span>
                    <span className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
                      {identity.current_roles.length} roles
                    </span>
                  </div>
                  <h2 className="mt-3 text-sm font-semibold text-slate-900 dark:text-white">
                    {identity.display_name}
                  </h2>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                    {identity.id}
                  </p>
                </button>
              ))}
            </div>
          )}
          {(identitiesQuery.data?.total ?? 0) > PAGE_SIZE && (
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page === 1}
                className="btn-secondary px-3 py-2 text-xs"
              >
                Previous
              </button>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Page {identitiesQuery.data?.page ?? page}
              </span>
              <button
                type="button"
                onClick={() => setPage((current) => current + 1)}
                disabled={identities.length < PAGE_SIZE}
                className="btn-secondary px-3 py-2 text-xs"
              >
                Next
              </button>
            </div>
          )}
        </div>

        {selectedIdentity ? (
          accessQuery.isLoading ? (
            <LoadingSpinner message="Loading identity evidence access..." />
          ) : accessQuery.isError ? (
            <GovernanceErrorState error={accessQuery.error} feature="identity evidence access" />
          ) : accessQuery.data ? (
            <div className="space-y-5">
              <div className="card p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    {selectedIdentity.identity_type}
                  </span>
                  <span className="badge bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-300">
                    Tenant {accessQuery.data.tenant_id}
                  </span>
                </div>
                <h2 className="mt-3 text-xl font-semibold text-slate-900 dark:text-white">
                  {selectedIdentity.display_name}
                </h2>
                <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
                  Inspecting raw entitlement edges for identity {accessQuery.data.identity_id}.
                </p>
                <div className="mt-4">
                  <Link
                    to={`/projects/${projectId}/identities/${selectedIdentity.id}`}
                    className="inline-flex text-sm font-semibold text-brand-600 hover:text-brand-700 dark:text-brand-400"
                  >
                    Open identity detail
                  </Link>
                </div>
              </div>

              <div className="card p-5">
                <h2 className="section-title">Effective access edges</h2>
                {accessQuery.data.items.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                    No access edges were returned for this identity.
                  </p>
                ) : (
                  <div className="mt-4 space-y-3">
                    {accessQuery.data.items.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-800/40"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-slate-900 dark:text-white">
                              {item.entitlement_id}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {item.edge_type} via {item.source}
                            </p>
                          </div>
                          <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                            {(item.confidence * 100).toFixed(0)}% confidence
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-1 gap-3 text-xs text-slate-500 dark:text-slate-400 md:grid-cols-2">
                          <p>Observed: {formatDateTime(item.observed_at)}</p>
                          <p>Valid to: {formatDateTime(item.valid_to)}</p>
                          <p>Scope: {item.scope_id ?? "None"}</p>
                          <p>Assignment: {item.assignment_id ?? "None"}</p>
                        </div>
                        {item.provenance.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {item.provenance.map((entry) => (
                              <span
                                key={entry}
                                className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                              >
                                {entry}
                              </span>
                            ))}
                          </div>
                        )}
                        {item.condition && (
                          <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">
                            Condition: {item.condition}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : null
        ) : (
          <EmptyState
            title="Select an identity"
            description="Choose an identity to inspect the access evidence returned by the backend."
          />
        )}
      </div>
    </div>
  );
}
