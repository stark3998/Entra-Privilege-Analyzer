from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.governance import (
    ApprovalPolicy,
    GovernanceWorkflow,
    RiskAssessment,
    WorkflowKind,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.authorization_governance import (
    AuthorizationGovernanceService,
    PolicyDecision,
)

_MIGRATION_STEPS = (
    "freeze_evidence",
    "evaluate_policy",
    "agent_proposal",
    "dry_run",
    "capture_snapshot",
    "approval",
    "create_or_reuse_role",
    "assign_replacement",
    "canary_validation",
    "grace_period",
    "remove_old_access",
    "verify_postconditions",
)


class GovernanceWorkflowService:
    """Creates and transitions deterministic, restart-safe governance workflows."""

    def __init__(self, authorization: AuthorizationGovernanceService) -> None:
        self._authorization = authorization

    def create_migration(
        self,
        *,
        tenant_id: str,
        project_id: str,
        identity_id: str,
        requested_by: str,
        idempotency_key: str,
        persona_id: str | None = None,
        risk_assessment_id: str | None = None,
    ) -> GovernanceWorkflow:
        now = datetime.now(UTC)
        return GovernanceWorkflow(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            identity_id=identity_id,
            kind=WorkflowKind.LEAST_PRIVILEGE_MIGRATION,
            status=WorkflowStatus.DRAFT,
            correlation_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            requested_by=requested_by,
            persona_id=persona_id,
            risk_assessment_id=risk_assessment_id,
            steps=[
                WorkflowStep(id=f"{index:02d}-{name}", name=name)
                for index, name in enumerate(_MIGRATION_STEPS, start=1)
            ],
            created_at=now,
            updated_at=now,
        )

    def apply_policy(
        self,
        workflow: GovernanceWorkflow,
        policy: ApprovalPolicy,
        assessment: RiskAssessment,
        *,
        role_tier: str,
        is_last_global_admin: bool = False,
    ) -> GovernanceWorkflow:
        decision = self._authorization.evaluate_remediation(
            policy,
            assessment,
            identity_id=workflow.identity_id,
            role_tier=role_tier,
            is_last_global_admin=is_last_global_admin,
        )
        if not decision.allowed:
            return workflow.model_copy(
                update={
                    "status": WorkflowStatus.FAILED,
                    "policy_decision": _decision_payload(decision),
                    "error": ", ".join(decision.reasons),
                    "updated_at": datetime.now(UTC),
                }
            )
        target = (
            WorkflowStatus.APPROVED
            if decision.autonomous
            else WorkflowStatus.WAITING_APPROVAL
        )
        return workflow.model_copy(
            update={
                "status": target,
                "policy_decision": _decision_payload(decision),
                "updated_at": datetime.now(UTC),
            }
        )

    def approve(
        self,
        workflow: GovernanceWorkflow,
        *,
        approver_id: str,
        approver_roles: list[str],
        policy: ApprovalPolicy,
    ) -> GovernanceWorkflow:
        self._authorization.require_capability(approver_roles, "workflow.approve")
        if workflow.requested_by == approver_id:
            raise ValueError("Requester cannot approve their own remediation workflow")
        approvals = [
            *workflow.approvals,
            {"approver_id": approver_id, "approved_at": datetime.now(UTC).isoformat()},
        ]
        unique_approvers = {item["approver_id"] for item in approvals}
        status = (
            WorkflowStatus.APPROVED
            if len(unique_approvers) >= policy.required_human_approvals
            else WorkflowStatus.WAITING_APPROVAL
        )
        return workflow.model_copy(
            update={
                "approvals": approvals,
                "status": status,
                "updated_at": datetime.now(UTC),
            }
        )

    def transition(
        self,
        workflow: GovernanceWorkflow,
        status: WorkflowStatus,
        *,
        error: str | None = None,
    ) -> GovernanceWorkflow:
        allowed = {
            WorkflowStatus.DRAFT: {
                WorkflowStatus.ANALYZING,
                WorkflowStatus.WAITING_APPROVAL,
                WorkflowStatus.APPROVED,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.ANALYZING: {
                WorkflowStatus.WAITING_APPROVAL,
                WorkflowStatus.APPROVED,
                WorkflowStatus.FAILED,
            },
            WorkflowStatus.WAITING_APPROVAL: {
                WorkflowStatus.APPROVED,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.APPROVED: {
                WorkflowStatus.EXECUTING,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.EXECUTING: {
                WorkflowStatus.CANARY,
                WorkflowStatus.VERIFYING,
                WorkflowStatus.FAILED,
                WorkflowStatus.COMPENSATING,
            },
            WorkflowStatus.CANARY: {
                WorkflowStatus.GRACE_PERIOD,
                WorkflowStatus.COMPENSATING,
            },
            WorkflowStatus.GRACE_PERIOD: {
                WorkflowStatus.VERIFYING,
                WorkflowStatus.COMPENSATING,
            },
            WorkflowStatus.VERIFYING: {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.COMPENSATING,
            },
            WorkflowStatus.COMPENSATING: {
                WorkflowStatus.RESTORED,
                WorkflowStatus.FAILED,
            },
        }
        if status not in allowed.get(workflow.status, set()):
            raise ValueError(f"Invalid workflow transition: {workflow.status} -> {status}")
        return workflow.model_copy(
            update={"status": status, "error": error, "updated_at": datetime.now(UTC)}
        )


def _decision_payload(decision: PolicyDecision) -> dict[str, object]:
    return {
        "allowed": decision.allowed,
        "autonomous": decision.autonomous,
        "requires_human_approval": decision.requires_human_approval,
        "reasons": list(decision.reasons),
    }
