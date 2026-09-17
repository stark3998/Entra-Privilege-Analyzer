import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  useApproveWorkflow,
  useGovernancePolicy,
  useIdentityDetail,
  useTransitionWorkflow,
  useWorkflowDetail,
} from "@/api/hooks";
import type { GovernanceWorkflowStatus } from "@/api/types";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import {
  WorkflowStatusBadge,
  WorkflowTypeBadge,
} from "@/components/governance/GovernanceBadges";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { useProjectContext } from "@/store/projectContext";
import { formatDateTime, toTitleCase } from "@/utils/governanceFormatting";
import { formatRelativeTime } from "@/utils/formatRelativeTime";

const TRANSITION_OPTIONS: GovernanceWorkflowStatus[] = [
  "draft",
  "analyzing",
  "waiting_approval",
  "approved",
  "executing",
  "canary",
  "grace_period",
  "verifying",
  "completed",
  "failed",
  "compensating",
  "restored",
  "cancelled",
];

export function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { projectId } = useProjectContext();
  const navigate = useNavigate();
  const { data, isLoading, isError, error } = useWorkflowDetail(id ?? "");
  const identityQuery = useIdentityDetail(data?.identity_id ?? "");
  const policyQuery = useGovernancePolicy();
  const approveMutation = useApproveWorkflow(id ?? "");
  const transitionMutation = useTransitionWorkflow(id ?? "");
  const [targetStatus, setTargetStatus] = useState<GovernanceWorkflowStatus>("approved");

  if (isLoading) {
    return <LoadingSpinner message="Loading workflow..." />;
  }

  if (isError) {
    return <EmptyState title="Failed to load workflow" description={error instanceof Error ? error.message : "An unexpected error occurred."} />;
  }

  if (!data) {
    return (
      <EmptyState
        title="Workflow not found"
        description="This workflow is not present in the current workflow list."
      />
    );
  }

  const identityLabel = identityQuery.data?.display_name ?? data.identity_id;

  return (
    <div className="space-y-6">
      <button
        type="button"
        onClick={() => navigate(`/projects/${projectId}/workflows`)}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm font-medium text-slate-600 transition-colors hover:bg-brand-50 hover:text-brand-700 dark:text-slate-400 dark:hover:bg-brand-900/20 dark:hover:text-brand-300"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
        Back to Workflow Inbox
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <WorkflowStatusBadge status={data.status} />
            <WorkflowTypeBadge type={data.kind} />
          </div>
          <h1 className="page-title mt-3">{identityLabel}</h1>
          <p className="page-subtitle">
            Workflow {data.id} requested by {data.requested_by} {formatRelativeTime(data.created_at)}
          </p>
        </div>
        <div className="text-right text-sm text-slate-500 dark:text-slate-400">
          <p>Updated {formatDateTime(data.updated_at)}</p>
          <p className="mt-1">Next wake {formatDateTime(data.next_wake_at)}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <GovernanceMetricCard label="Steps" value={data.steps.length} tone="brand" />
        <GovernanceMetricCard label="Approvals" value={data.approvals.length} tone="amber" />
        <GovernanceMetricCard label="Completed actions" value={data.completed_action_ids.length} tone="emerald" />
        <GovernanceMetricCard label="Policy keys" value={Object.keys(data.policy_decision).length} tone="slate" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="section-title">Workflow metadata</h2>
            <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Identity</p>
                <Link
                  to={`/projects/${projectId}/identities/${data.identity_id}`}
                  className="mt-1 inline-flex text-sm font-semibold text-brand-600 hover:text-brand-700 dark:text-brand-400"
                >
                  {identityLabel}
                </Link>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Persona</p>
                <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                  {data.persona_id ?? "None"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Risk assessment</p>
                <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                  {data.risk_assessment_id ?? "Not linked"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Snapshot</p>
                <p className="mt-1 text-sm font-medium text-slate-900 dark:text-white">
                  {data.snapshot_id ?? "Not linked"}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Correlation ID</p>
                <p className="mt-1 break-all text-sm font-medium text-slate-900 dark:text-white">
                  {data.correlation_id}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Idempotency key</p>
                <p className="mt-1 break-all text-sm font-medium text-slate-900 dark:text-white">
                  {data.idempotency_key}
                </p>
              </div>
            </div>
            {data.error && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                {data.error}
              </div>
            )}
          </section>

          <section className="card p-5">
            <h2 className="section-title">Execution steps</h2>
            {data.steps.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">No execution steps have been recorded yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {data.steps.map((step) => (
                  <div
                    key={step.id}
                    className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 dark:border-slate-700/80 dark:bg-slate-800/40"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">{step.name}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{step.id}</p>
                      </div>
                      <span className="badge bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                        {toTitleCase(step.status)}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-1 gap-3 text-xs text-slate-500 dark:text-slate-400 md:grid-cols-3">
                      <p>Started: {formatDateTime(step.started_at)}</p>
                      <p>Completed: {formatDateTime(step.completed_at)}</p>
                      <p>Action: {step.action_id ?? "None"}</p>
                    </div>
                    {step.error && (
                      <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                        {step.error}
                      </p>
                    )}
                    {Object.keys(step.details).length > 0 && (
                      <div className="mt-3">
                        <JsonViewer content={JSON.stringify(step.details, null, 2)} language="json" maxHeight="max-h-64" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <section className="card p-5">
            <h2 className="section-title">Supported actions</h2>
            <p className="mt-2 text-sm text-slate-700 dark:text-slate-300">
              Only the backend-supported workflow actions are exposed here.
            </p>
            <div className="mt-4 space-y-4">
              <button
                type="button"
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending || data.status !== "waiting_approval"}
                className="btn-primary"
              >
                {approveMutation.isPending ? "Approving..." : "Approve workflow"}
              </button>

              <div className="space-y-2">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Transition target
                </label>
                <select
                  value={targetStatus}
                  onChange={(event) => setTargetStatus(event.target.value as GovernanceWorkflowStatus)}
                  className="input-base w-full"
                >
                  {TRANSITION_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {toTitleCase(status)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => transitionMutation.mutate({ target: targetStatus })}
                  disabled={transitionMutation.isPending}
                  className="btn-secondary"
                >
                  {transitionMutation.isPending ? "Transitioning..." : "Apply transition"}
                </button>
              </div>

              {(approveMutation.isError || transitionMutation.isError) && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                  {approveMutation.error instanceof Error
                    ? approveMutation.error.message
                    : transitionMutation.error instanceof Error
                      ? transitionMutation.error.message
                      : "Workflow action failed."}
                </div>
              )}
            </div>
          </section>

          <section className="card p-5">
            <h2 className="section-title">Policy decision</h2>
            {Object.keys(data.policy_decision).length > 0 ? (
              <div className="mt-4">
                <JsonViewer content={JSON.stringify(data.policy_decision, null, 2)} language="json" maxHeight="max-h-72" />
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">No policy decision payload has been recorded yet.</p>
            )}
          </section>

          <section className="card p-5">
            <h2 className="section-title">Approvals</h2>
            {data.approvals.length > 0 ? (
              <div className="mt-4">
                <JsonViewer content={JSON.stringify(data.approvals, null, 2)} language="json" maxHeight="max-h-72" />
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">No approvals have been recorded yet.</p>
            )}
          </section>

          {policyQuery.data && (
            <section className="card p-5">
              <h2 className="section-title">Approval policy snapshot</h2>
              <div className="mt-4 grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Authorization mode</p>
                  <p className="mt-1 font-medium text-slate-900 dark:text-white">
                    {toTitleCase(policyQuery.data.authorization_mode)}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Human approvals</p>
                  <p className="mt-1 font-medium text-slate-900 dark:text-white">
                    {policyQuery.data.required_human_approvals}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Max autonomous impact</p>
                  <p className="mt-1 font-medium text-slate-900 dark:text-white">
                    {policyQuery.data.autonomous_max_impact}%
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Min autonomous confidence</p>
                  <p className="mt-1 font-medium text-slate-900 dark:text-white">
                    {policyQuery.data.autonomous_min_confidence}
                  </p>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
