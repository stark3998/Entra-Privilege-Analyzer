import { useState } from "react";
import { useAuthorizationReadiness, useGovernancePolicy, useRunScopedCopilot } from "@/api/hooks";
import type { GovernanceCopilotResponse } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { GovernanceErrorState } from "@/components/governance/GovernanceFeedback";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { formatDateTime, toTitleCase } from "@/utils/governanceFormatting";

interface CopilotQueryResult {
  id: string;
  query: string;
  scopeText: string;
  submittedAt: string;
  response: GovernanceCopilotResponse;
}

export function ScopedCopilotPage() {
  const readinessQuery = useAuthorizationReadiness();
  const policyQuery = useGovernancePolicy();
  const queryMutation = useRunScopedCopilot();
  const [query, setQuery] = useState("");
  const [scopeText, setScopeText] = useState("{}");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [history, setHistory] = useState<CopilotQueryResult[]>([]);

  if (policyQuery.isError) {
    return <GovernanceErrorState error={policyQuery.error} feature="governance policy" />;
  }

  if (readinessQuery.isError) {
    return <GovernanceErrorState error={readinessQuery.error} feature="authorization readiness" />;
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setValidationError(null);

    let scope: Record<string, unknown>;
    try {
      const parsed = JSON.parse(scopeText);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        setValidationError("Scope must be a JSON object.");
        return;
      }
      scope = parsed as Record<string, unknown>;
    } catch {
      setValidationError("Scope must be valid JSON.");
      return;
    }

    queryMutation.mutate(
      { query: query.trim(), scope },
      {
        onSuccess: (response) => {
          const submittedAt = new Date().toISOString();
          setHistory((current) => [
            {
              id: `${submittedAt}-${current.length}`,
              query: query.trim(),
              scopeText,
              submittedAt,
              response,
            },
            ...current,
          ]);
          setQuery("");
        },
      },
    );
  }

  const policy = policyQuery.data;
  const readiness = readinessQuery.data;
  const latest = history[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Scoped Copilot</h1>
        <p className="page-subtitle">
          Query the governance copilot using the backend-supported query payload and inspect the raw response
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <GovernanceMetricCard label="Queries this session" value={history.length} tone="brand" />
        <GovernanceMetricCard
          label="Authorization ready"
          value={readiness?.ready ? "Yes" : "No"}
          tone={readiness?.ready ? "emerald" : "amber"}
        />
        <GovernanceMetricCard
          label="Policy loaded"
          value={policy ? "Yes" : "No"}
          tone={policy ? "slate" : "amber"}
        />
      </div>

      {readiness && (
        <div
          className={`card p-4 text-sm ${
            readiness.ready
              ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20"
              : "border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20"
          }`}
        >
          <p className="font-semibold text-slate-900 dark:text-white">Authorization readiness</p>
          <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <p>Mode: {toTitleCase(readiness.mode)}</p>
            <p>Collection: {readiness.collection_ready ? "Ready" : "Not ready"}</p>
            <p>Mutation: {readiness.mutation_ready ? "Ready" : "Not ready"}</p>
            <p>Delegated: {readiness.delegated_ready ? "Ready" : "Not ready"}</p>
          </div>
          {(readiness.missing.length > 0 || readiness.warnings.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-2">
              {readiness.missing.map((item) => (
                <span
                  key={item}
                  className="rounded-full bg-white/80 px-2.5 py-1 text-xs font-medium text-red-700 dark:bg-slate-900/50 dark:text-red-300"
                >
                  Missing: {item}
                </span>
              ))}
              {readiness.warnings.map((item) => (
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

      {policy && (
        <div className="card p-5">
          <h2 className="section-title">Approval policy snapshot</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 text-sm md:grid-cols-2 xl:grid-cols-4">
            <p>Authorization mode: {toTitleCase(policy.authorization_mode)}</p>
            <p>Autonomous max impact: {policy.autonomous_max_impact}%</p>
            <p>Min confidence: {policy.autonomous_min_confidence}</p>
            <p>Required approvals: {policy.required_human_approvals}</p>
          </div>
          {policy.break_glass_identity_ids.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {policy.break_glass_identity_ids.map((identityId) => (
                <span
                  key={identityId}
                  className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                >
                  Break glass: {identityId}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr,1.25fr]">
        <div className="card p-5">
          <h2 className="section-title">Run query</h2>
          <p className="page-subtitle mt-1">
            The backend expects a raw query string plus a JSON scope object.
          </p>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">
                Query
              </label>
              <textarea
                rows={5}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="input-base mt-1.5 w-full"
                placeholder="Summarize the governance posture for this project."
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">
                Scope JSON
              </label>
              <textarea
                rows={8}
                value={scopeText}
                onChange={(event) => setScopeText(event.target.value)}
                className="input-base mt-1.5 w-full font-mono text-sm"
                spellCheck={false}
              />
            </div>
            {(validationError || queryMutation.isError) && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                {validationError ??
                  (queryMutation.error instanceof Error
                    ? queryMutation.error.message
                    : "Failed to run governance copilot query.")}
              </div>
            )}
            <button
              type="submit"
              disabled={!query.trim() || queryMutation.isPending}
              className="btn-primary"
            >
              {queryMutation.isPending ? "Querying..." : "Run scoped copilot"}
            </button>
          </form>
        </div>

        <div className="space-y-5">
          <div className="card p-5">
            <h2 className="section-title">Latest response</h2>
            {latest ? (
              <div className="mt-4 space-y-4">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Submitted</p>
                  <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                    {formatDateTime(latest.submittedAt)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Answer</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300">
                    {latest.response.answer}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Raw response</p>
                  <div className="mt-2">
                    <JsonViewer content={JSON.stringify(latest.response, null, 2)} language="json" maxHeight="max-h-80" />
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState
                title="No scoped queries yet"
                description="Run a governance copilot query to inspect the raw backend response."
              />
            )}
          </div>

          {history.length > 1 && (
            <div className="card p-5">
              <h2 className="section-title">Recent session queries</h2>
              <div className="mt-4 space-y-3">
                {history.slice(1).map((item) => (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-800/40"
                  >
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{item.query}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {formatDateTime(item.submittedAt)}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
