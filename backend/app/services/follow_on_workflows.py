from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.governance import (
    GovernanceWorkflow,
    WorkflowKind,
    WorkflowStatus,
    WorkflowStep,
)

_STEPS: dict[WorkflowKind, tuple[str, ...]] = {
    WorkflowKind.CONTINUOUS_DRIFT: (
        "evaluate_drift",
        "collect_context",
        "policy_decision",
        "contain_or_notify",
        "verify",
    ),
    WorkflowKind.JIT_ACCESS: (
        "validate_request",
        "evaluate_risk",
        "approval",
        "activate_pim",
        "monitor_session",
        "expire_and_verify",
    ),
    WorkflowKind.INCIDENT_CONTAINMENT: (
        "freeze_evidence",
        "capture_snapshot",
        "contain",
        "investigate",
        "approval",
        "recover",
        "verify",
    ),
    WorkflowKind.ACCESS_REVIEW: (
        "select_population",
        "collect_evidence",
        "generate_decisions",
        "owner_review",
        "apply_decisions",
        "verify",
    ),
    WorkflowKind.RESTORE: (
        "verify_snapshot",
        "three_way_diff",
        "conflict_approval",
        "apply_inverse_operations",
        "verify",
    ),
}


def create_follow_on_workflow(
    *,
    kind: WorkflowKind,
    tenant_id: str,
    project_id: str,
    identity_id: str,
    requested_by: str,
    idempotency_key: str,
) -> GovernanceWorkflow:
    if kind not in _STEPS:
        raise ValueError(f"{kind} is not a follow-on workflow")
    now = datetime.now(UTC)
    return GovernanceWorkflow(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        project_id=project_id,
        identity_id=identity_id,
        kind=kind,
        status=WorkflowStatus.DRAFT,
        correlation_id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        requested_by=requested_by,
        steps=[
            WorkflowStep(id=f"{index:02d}-{name}", name=name)
            for index, name in enumerate(_STEPS[kind], start=1)
        ],
        created_at=now,
        updated_at=now,
    )
