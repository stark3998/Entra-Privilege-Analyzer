from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.governance import (
    AccessEdgeSnapshot,
    ApprovalPolicy,
    GovernanceWorkflow,
    RiskAssessment,
    WorkflowStatus,
)
from app.models.remediation import RemediationAction, RemediationActionType
from app.services.authorization_governance import AuthorizationGovernanceService
from app.services.governance_repo import GovernanceRepo
from app.services.governance_workflow import GovernanceWorkflowService
from app.services.provider_errors import ProviderOperationError
from app.services.remediation_engine import RemediationEngine
from app.services.snapshot_restore import SnapshotRestoreService

TokenProvider = Callable[[str], Awaitable[str]]


class RemediationSaga:
    """Deterministic least-privilege saga; durable hosts checkpoint each method call."""

    def __init__(
        self,
        governance_repo: GovernanceRepo,
        remediation_engine: RemediationEngine,
        snapshot_service: SnapshotRestoreService,
        token_provider: TokenProvider,
    ) -> None:
        self._repo = governance_repo
        self._remediation = remediation_engine
        self._snapshots = snapshot_service
        self._token_provider = token_provider
        self._workflow_service = GovernanceWorkflowService(
            AuthorizationGovernanceService()
        )

    async def prepare(
        self,
        workflow: GovernanceWorkflow,
        *,
        policy: ApprovalPolicy,
        assessment: RiskAssessment,
        role_tier: str,
        current_edges: list[AccessEdgeSnapshot],
        actor: str,
        evidence_days: int,
        evidence_completeness: float,
        is_last_global_admin: bool = False,
    ) -> GovernanceWorkflow:
        if evidence_days < 90 or evidence_completeness < 0.9:
            failed = workflow.model_copy(
                update={
                    "status": WorkflowStatus.FAILED,
                    "error": "Evidence baseline is below the minimum safety threshold",
                    "updated_at": datetime.now(UTC),
                }
            )
            return await self._repo.upsert_workflow(failed)
        snapshot = self._snapshots.create_snapshot(
            tenant_id=workflow.tenant_id,
            project_id=workflow.project_id,
            identity_id=workflow.identity_id,
            workflow_id=workflow.id,
            edges=current_edges,
            created_by=actor,
        )
        await self._repo.upsert_snapshot(snapshot)
        evaluated = self._workflow_service.apply_policy(
            workflow.model_copy(update={"snapshot_id": snapshot.id}),
            policy,
            assessment,
            role_tier=role_tier,
            is_last_global_admin=is_last_global_admin,
        )
        return await self._repo.upsert_workflow(evaluated)

    async def execute(
        self,
        workflow: GovernanceWorkflow,
        action_specs: list[dict[str, Any]],
        *,
        grace_period_hours: int = 24,
    ) -> GovernanceWorkflow:
        if workflow.status != WorkflowStatus.APPROVED:
            raise ValueError("Workflow must be approved before execution")
        for spec in action_specs:
            RemediationActionType(spec["action_type"])
        executing = self._workflow_service.transition(
            workflow, WorkflowStatus.EXECUTING
        )
        await self._repo.upsert_workflow(executing)
        token = await self._token_provider(workflow.tenant_id)
        completed_actions: list[RemediationAction] = []
        try:
            for index, spec in enumerate(action_specs):
                action = await self._remediation.request_action(
                    tenant_id=workflow.tenant_id,
                    project_id=workflow.project_id,
                    action_type=RemediationActionType(spec["action_type"]),
                    target_identity_id=workflow.identity_id,
                    target_resource_id=spec.get("target_resource_id"),
                    requested_by=workflow.requested_by,
                    justification=f"Workflow {workflow.id}",
                    idempotency_key=f"{workflow.id}:{index}",
                    correlation_id=workflow.correlation_id,
                    provider=spec.get("provider", "microsoft_graph"),
                    provider_payload=spec.get("provider_payload", {}),
                    preconditions=spec.get("preconditions", []),
                    postconditions=spec.get("postconditions", []),
                    compensation=spec.get("compensation"),
                    dry_run=bool(spec.get("dry_run", False)),
                )
                approved = await self._remediation.approve_action(
                    workflow.tenant_id,
                    action.id,
                    "workflow-policy",
                )
                completed_actions.append(
                    await self._remediation.execute_action(
                        workflow.tenant_id,
                        approved.id,
                        token,
                    )
                )
                executing = executing.model_copy(
                    update={
                        "completed_action_ids": [
                            *executing.completed_action_ids,
                            completed_actions[-1].id,
                        ],
                        "updated_at": datetime.now(UTC),
                    }
                )
                await self._repo.upsert_workflow(executing)
        except ProviderOperationError:
            compensating = self._workflow_service.transition(
                executing, WorkflowStatus.COMPENSATING
            )
            await self._repo.upsert_workflow(compensating)
            await self._compensate(workflow, completed_actions, token)
            restored = self._workflow_service.transition(
                compensating, WorkflowStatus.RESTORED
            )
            await self._repo.upsert_workflow(restored)
            raise
        canary = self._workflow_service.transition(executing, WorkflowStatus.CANARY)
        canary = canary.model_copy(
            update={"next_wake_at": datetime.now(UTC) + timedelta(hours=grace_period_hours)}
        )
        return await self._repo.upsert_workflow(canary)

    async def complete_canary(
        self,
        workflow: GovernanceWorkflow,
        *,
        canary_passed: bool,
    ) -> GovernanceWorkflow:
        if workflow.status != WorkflowStatus.CANARY:
            raise ValueError("Workflow is not in canary validation")
        target = (
            WorkflowStatus.GRACE_PERIOD
            if canary_passed
            else WorkflowStatus.COMPENSATING
        )
        transitioned = self._workflow_service.transition(workflow, target)
        await self._repo.upsert_workflow(transitioned)
        if canary_passed:
            return transitioned

        completed_actions = [
            await self._remediation.get_action(workflow.tenant_id, action_id)
            for action_id in workflow.completed_action_ids
        ]
        token = await self._token_provider(workflow.tenant_id)
        await self._compensate(workflow, completed_actions, token)
        restored = self._workflow_service.transition(
            transitioned,
            WorkflowStatus.RESTORED,
        )
        return await self._repo.upsert_workflow(restored)

    async def _compensate(
        self,
        workflow: GovernanceWorkflow,
        completed_actions: list[RemediationAction],
        token: str,
    ) -> None:
        for index, action in enumerate(reversed(completed_actions)):
            if not action.compensation:
                continue
            compensation = action.compensation
            inverse = await self._remediation.request_action(
                tenant_id=workflow.tenant_id,
                project_id=workflow.project_id,
                action_type=action.action_type,
                target_identity_id=workflow.identity_id,
                target_resource_id=action.target_resource_id,
                requested_by="workflow-compensation",
                justification=f"Compensation for {action.id}",
                idempotency_key=f"{workflow.id}:compensation:{index}",
                correlation_id=workflow.correlation_id,
                provider=action.provider,
                provider_payload=compensation,
            )
            approved = await self._remediation.approve_action(
                workflow.tenant_id,
                inverse.id,
                "workflow-compensation",
            )
            await self._remediation.execute_action(
                workflow.tenant_id,
                approved.id,
                token,
            )
