import { useMemo, useState } from "react";
import { useWorkflowInbox } from "@/api/hooks";
import type { GovernanceWorkflow } from "@/api/types";
import { WorkflowInboxList } from "@/components/governance/WorkflowInboxList";
import { GovernanceMetricCard } from "@/components/governance/GovernanceMetricCard";
import { GovernanceErrorState } from "@/components/governance/GovernanceFeedback";
import { useProjectContext } from "@/store/projectContext";
import { MotionItem, MotionStagger } from "@/components/common/motion";

const PAGE_SIZE = 12;

function matchesWorkflow(workflow: GovernanceWorkflow, search: string) {
  if (!search) return true;
  const needle = search.toLowerCase();
  return [
    workflow.id,
    workflow.identity_id,
    workflow.requested_by,
    workflow.persona_id,
    workflow.risk_assessment_id,
    workflow.snapshot_id,
    workflow.error,
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

export function WorkflowInboxPage() {
  const { projectId } = useProjectContext();
  const [status, setStatus] = useState("");
  const [workflowType, setWorkflowType] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError, error } = useWorkflowInbox();

  const filtered = useMemo(() => {
    const items = data ?? [];
    return items.filter((workflow) => {
      if (status && workflow.status !== status) return false;
      if (workflowType && workflow.kind !== workflowType) return false;
      return matchesWorkflow(workflow, search.trim());
    });
  }, [data, search, status, workflowType]);

  const metrics = useMemo(
    () => ({
      waitingApproval: filtered.filter((workflow) => workflow.status === "waiting_approval").length,
      inFlight: filtered.filter((workflow) =>
        ["analyzing", "executing", "canary", "grace_period", "verifying", "compensating"].includes(workflow.status),
      ).length,
      failed: filtered.filter((workflow) => workflow.status === "failed").length,
      completed: filtered.filter((workflow) =>
        ["completed", "restored", "cancelled"].includes(workflow.status),
      ).length,
    }),
    [filtered],
  );

  const start = (page - 1) * PAGE_SIZE;
  const items = filtered.slice(start, start + PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Governance Workflows</p>
          <h1 className="page-title mt-1">Workflow Inbox</h1>
          <p className="page-subtitle">
            Review active governance workflows, approval state, and referenced remediation artifacts
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            className="input-base py-2"
            aria-label="Filter workflow status"
          >
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="analyzing">Analyzing</option>
            <option value="waiting_approval">Waiting approval</option>
            <option value="approved">Approved</option>
            <option value="executing">Executing</option>
            <option value="canary">Canary</option>
            <option value="grace_period">Grace period</option>
            <option value="verifying">Verifying</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="compensating">Compensating</option>
            <option value="restored">Restored</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            value={workflowType}
            onChange={(event) => {
              setWorkflowType(event.target.value);
              setPage(1);
            }}
            className="input-base py-2"
            aria-label="Filter workflow type"
          >
            <option value="">All workflow types</option>
            <option value="least_privilege_migration">Least privilege migration</option>
            <option value="continuous_drift">Continuous drift</option>
            <option value="jit_access">JIT access</option>
            <option value="incident_containment">Incident containment</option>
            <option value="access_review">Access review</option>
            <option value="restore">Restore</option>
          </select>
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="input-base min-w-64 py-2"
            placeholder="Search workflow, identity, persona, or artifact ID"
            aria-label="Search workflows"
          />
        </div>
      </div>

      <MotionStagger className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MotionItem><GovernanceMetricCard label="Waiting approval" value={metrics.waitingApproval} tone="amber" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="In flight" value={metrics.inFlight} tone="brand" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="Failed" value={metrics.failed} tone="red" /></MotionItem>
        <MotionItem><GovernanceMetricCard label="Completed" value={metrics.completed} tone="emerald" /></MotionItem>
      </MotionStagger>

      {isError ? (
        <GovernanceErrorState error={error} feature="workflow inbox" />
      ) : (
        <WorkflowInboxList
          items={items}
          total={filtered.length}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          basePath={`/projects/${projectId}/workflows`}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}
