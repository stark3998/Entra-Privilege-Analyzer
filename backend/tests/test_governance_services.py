from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import Settings
from app.models.governance import (
    AccessEdgeSnapshot,
    ApprovalPolicy,
    AuthorizationConfiguration,
    AuthorizationMode,
    ConnectorConfig,
    ConnectorDelivery,
    ConnectorType,
    GovernanceRole,
    SafetyMetrics,
    WorkflowStatus,
)
from app.models.identity import CurrentRole, IdentityProfile, IdentityType, ObservedAction
from app.models.remediation import (
    RemediationAction,
    RemediationActionType,
    RemediationStatus,
)
from app.models.tenant_evidence import ActivityEvidence
from app.services.access_providers import GraphAccessProvider
from app.services.agent_gateway import AgentGateway
from app.services.authorization_governance import AuthorizationGovernanceService
from app.services.authorization_readiness import AuthorizationReadinessService
from app.services.connectors import (
    ConnectorDeliveryError,
    ConnectorDeliveryWorker,
    ConnectorDispatcher,
    KeyVaultSecretResolver,
)
from app.services.crypto import CryptoService
from app.services.evidence_aggregator import EvidenceAggregator
from app.services.governance_workflow import GovernanceWorkflowService
from app.services.provider_errors import ProviderFailureCategory, ProviderOperationError
from app.services.remediation_saga import RemediationSaga
from app.services.risk_confidence_engine import RiskConfidenceEngine
from app.services.safety_gates import SafetyGateEvaluator
from app.services.snapshot_restore import SnapshotRestoreService


class _SagaRepo:
    def __init__(self) -> None:
        self.workflows = []
        self.snapshots = []

    async def upsert_workflow(self, workflow):
        self.workflows.append(workflow)
        return workflow

    async def upsert_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        return snapshot


class _SagaRemediation:
    def __init__(self, fail_at: int | None = None) -> None:
        self.actions: dict[str, RemediationAction] = {}
        self.requests: list[RemediationAction] = []
        self.executions: list[str] = []
        self.fail_at = fail_at

    async def request_action(self, **kwargs) -> RemediationAction:
        action = RemediationAction(
            id=f"action-{len(self.requests) + 1}",
            tenant_id=kwargs["tenant_id"],
            project_id=kwargs["project_id"],
            correlation_id=kwargs["correlation_id"],
            idempotency_key=kwargs["idempotency_key"],
            action_type=kwargs["action_type"],
            target_identity_id=kwargs["target_identity_id"],
            target_resource_id=kwargs.get("target_resource_id"),
            requested_by=kwargs["requested_by"],
            justification=kwargs["justification"],
            created_at=datetime.now(UTC),
            provider=kwargs["provider"],
            provider_payload=kwargs["provider_payload"],
            compensation=kwargs.get("compensation"),
        )
        self.actions[action.id] = action
        self.requests.append(action)
        return action

    async def approve_action(
        self,
        tenant_id: str,
        action_id: str,
        approver: str,
    ) -> RemediationAction:
        action = self.actions[action_id].model_copy(
            update={"status": RemediationStatus.APPROVED, "approved_by": approver}
        )
        self.actions[action_id] = action
        return action

    async def execute_action(
        self,
        tenant_id: str,
        action_id: str,
        token: str,
    ) -> RemediationAction:
        self.executions.append(action_id)
        if self.fail_at == len(self.executions):
            raise ProviderOperationError(
                ProviderFailureCategory.TRANSIENT,
                "provider unavailable",
                provider="test",
                retryable=True,
            )
        action = self.actions[action_id].model_copy(
            update={"status": RemediationStatus.COMPLETED}
        )
        self.actions[action_id] = action
        return action

    async def get_action(
        self,
        tenant_id: str,
        action_id: str,
    ) -> RemediationAction:
        return self.actions[action_id]


class _ConnectorRepo:
    def __init__(
        self,
        connector: ConnectorConfig,
        delivery: ConnectorDelivery,
    ) -> None:
        self.connector = connector
        self.delivery = delivery

    async def list_due_deliveries(self, project_id: str, *, now, limit: int):
        return [self.delivery]

    async def get_connector(self, connector_id: str, project_id: str):
        return self.connector

    async def upsert_delivery(self, delivery: ConnectorDelivery):
        self.delivery = delivery
        return delivery


def _identity() -> IdentityProfile:
    now = datetime.now(UTC)
    return IdentityProfile(
        id="User-user-1",
        tenant_id="tenant-1",
        identity_type=IdentityType.USER,
        object_id="user-1",
        display_name="User One",
        current_roles=[
            CurrentRole(
                role_id="role-1",
                role_name="Global Administrator",
                is_permanent=True,
            )
        ],
        observed_actions=[
            ObservedAction(
                action="Read users",
                count=10,
                first_seen=now - timedelta(days=90),
                last_seen=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )


def test_risk_assessment_separates_dimensions() -> None:
    assessment = RiskConfidenceEngine().assess(
        _identity(),
        drift_score=60,
        unused_permission_ratio=0.5,
        peer_deviation=40,
        seasonal_deviation=20,
        evidence_coverage=0.8,
        evidence_days=90,
    )
    assert assessment.risk == 45
    assert assessment.impact == 30
    assert assessment.confidence == 0.8
    assert {component.name for component in assessment.components} == {
        "drift",
        "unused_privilege",
        "peer_deviation",
        "seasonal_deviation",
    }


def test_policy_blocks_break_glass_and_requires_human_for_high_impact() -> None:
    now = datetime.now(UTC)
    policy = ApprovalPolicy(
        project_id="project-1",
        break_glass_identity_ids=["break-glass"],
        created_at=now,
        updated_at=now,
        updated_by="admin",
    )
    assessment = RiskConfidenceEngine().assess(
        _identity(),
        drift_score=10,
        unused_permission_ratio=0.1,
        peer_deviation=5,
        seasonal_deviation=5,
        evidence_coverage=1,
        evidence_days=90,
    )
    service = AuthorizationGovernanceService()
    blocked = service.evaluate_remediation(
        policy,
        assessment,
        identity_id="break-glass",
        role_tier="low",
    )
    assert not blocked.allowed
    service.require_capability([GovernanceRole.REMEDIATION_APPROVER], "workflow.approve")
    service.require_capability(["IAMAdmin"], "restore.execute")
    service.require_capability(["IAMAdmin"], "incident.execute")
    service.require_capability(["SecurityEngineer"], "policy.read")


def test_workflow_requires_separate_approver() -> None:
    now = datetime.now(UTC)
    policy = ApprovalPolicy(
        project_id="project-1",
        created_at=now,
        updated_at=now,
        updated_by="admin",
    )
    service = GovernanceWorkflowService(AuthorizationGovernanceService())
    workflow = service.create_migration(
        tenant_id="tenant-1",
        project_id="project-1",
        identity_id="identity-1",
        requested_by="requester",
        idempotency_key="key-1",
    ).model_copy(update={"status": WorkflowStatus.WAITING_APPROVAL})
    with pytest.raises(ValueError):
        service.approve(
            workflow,
            approver_id="requester",
            approver_roles=[GovernanceRole.REMEDIATION_APPROVER],
            policy=policy,
        )


def test_snapshot_integrity_and_three_way_restore() -> None:
    key = base64.b64encode(b"k" * 32).decode()
    service = SnapshotRestoreService(CryptoService(Settings(encryption_key=key)))
    original = AccessEdgeSnapshot(
        id="edge-1",
        principal_id="identity-1",
        entitlement_id="role-1",
        edge_type="direct",
        source="graph",
    )
    snapshot = service.create_snapshot(
        tenant_id="tenant-1",
        project_id="project-1",
        identity_id="identity-1",
        workflow_id="workflow-1",
        edges=[original],
        created_by="admin",
    )
    plan = service.build_restore_plan(snapshot, [], {"edge-1"})
    assert plan.restore_edges == [original]
    assert not plan.conflicts
    tampered = snapshot.model_copy(update={"payload_hash": "bad"})
    with pytest.raises(ValueError, match="integrity"):
        service.read_snapshot(tampered)


def test_activity_aggregates_hour_day_and_week() -> None:
    event = ActivityEvidence(
        id="event-1",
        tenant_id="tenant-1",
        principal_id="identity-1",
        action="Read users",
        source="audit",
        occurred_at=datetime(2026, 9, 15, 4, 30, tzinfo=UTC),
        evidence_id="evidence-1",
    )
    aggregates = EvidenceAggregator().aggregate([event])
    assert {item.bucket for item in aggregates} == {"hour", "day", "week"}
    assert all(item.count == 1 for item in aggregates)


@pytest.mark.asyncio
async def test_saga_prepare_enforces_evidence_and_approval_policy() -> None:
    now = datetime.now(UTC)
    key = base64.b64encode(b"k" * 32).decode()
    repo = _SagaRepo()
    saga = RemediationSaga(
        repo,
        _SagaRemediation(),
        SnapshotRestoreService(CryptoService(Settings(encryption_key=key))),
        lambda tenant_id: _token("token"),
    )
    workflow = GovernanceWorkflowService(
        AuthorizationGovernanceService()
    ).create_migration(
        tenant_id="tenant-1",
        project_id="project-1",
        identity_id="identity-1",
        requested_by="requester",
        idempotency_key="saga-prepare",
    )
    assessment = RiskConfidenceEngine().assess(
        _identity(),
        drift_score=10,
        unused_permission_ratio=0.1,
        peer_deviation=5,
        seasonal_deviation=5,
        evidence_coverage=1,
        evidence_days=90,
    )
    policy = ApprovalPolicy(
        project_id="project-1",
        autonomous_max_impact=100,
        autonomous_min_confidence=0,
        created_at=now,
        updated_at=now,
        updated_by="admin",
    )

    rejected = await saga.prepare(
        workflow,
        policy=policy,
        assessment=assessment,
        role_tier="low",
        current_edges=[],
        actor="admin",
        evidence_days=89,
        evidence_completeness=1,
    )
    assert rejected.status == WorkflowStatus.FAILED
    assert not repo.snapshots

    approved = await saga.prepare(
        workflow.model_copy(update={"id": "workflow-approved"}),
        policy=policy,
        assessment=assessment,
        role_tier="low",
        current_edges=[],
        actor="admin",
        evidence_days=90,
        evidence_completeness=0.9,
    )
    assert approved.status == WorkflowStatus.APPROVED
    assert approved.snapshot_id

    waiting = await saga.prepare(
        workflow.model_copy(update={"id": "workflow-waiting"}),
        policy=policy.model_copy(update={"autonomous_max_impact": 0}),
        assessment=assessment,
        role_tier="low",
        current_edges=[],
        actor="admin",
        evidence_days=90,
        evidence_completeness=0.9,
    )
    assert waiting.status == WorkflowStatus.WAITING_APPROVAL


@pytest.mark.asyncio
async def test_saga_failed_canary_compensates_in_reverse_order() -> None:
    repo = _SagaRepo()
    remediation = _SagaRemediation()
    saga = RemediationSaga(
        repo,
        remediation,
        object(),
        lambda tenant_id: _token("token"),
    )
    workflow = GovernanceWorkflowService(
        AuthorizationGovernanceService()
    ).create_migration(
        tenant_id="tenant-1",
        project_id="project-1",
        identity_id="identity-1",
        requested_by="requester",
        idempotency_key="saga-canary",
    ).model_copy(update={"status": WorkflowStatus.APPROVED})
    canary = await saga.execute(
        workflow,
        [
            {
                "action_type": "assign_entra_role",
                "provider_payload": {"operation": "apply-1"},
                "compensation": {"operation": "undo-1"},
            },
            {
                "action_type": "remove_role",
                "provider_payload": {"operation": "apply-2"},
                "compensation": {"operation": "undo-2"},
            },
        ],
        grace_period_hours=1,
    )
    assert canary.status == WorkflowStatus.CANARY
    assert canary.completed_action_ids == ["action-1", "action-2"]

    restored = await saga.complete_canary(canary, canary_passed=False)
    assert restored.status == WorkflowStatus.RESTORED
    assert [
        action.provider_payload["operation"] for action in remediation.requests[2:]
    ] == ["undo-2", "undo-1"]


@pytest.mark.asyncio
async def test_saga_provider_failure_restores_completed_changes() -> None:
    repo = _SagaRepo()
    remediation = _SagaRemediation(fail_at=2)
    saga = RemediationSaga(
        repo,
        remediation,
        object(),
        lambda tenant_id: _token("token"),
    )
    workflow = GovernanceWorkflowService(
        AuthorizationGovernanceService()
    ).create_migration(
        tenant_id="tenant-1",
        project_id="project-1",
        identity_id="identity-1",
        requested_by="requester",
        idempotency_key="saga-provider-failure",
    ).model_copy(update={"status": WorkflowStatus.APPROVED})

    with pytest.raises(ProviderOperationError):
        await saga.execute(
            workflow,
            [
                {
                    "action_type": "assign_entra_role",
                    "provider_payload": {"operation": "apply-1"},
                    "compensation": {"operation": "undo-1"},
                },
                {
                    "action_type": "remove_role",
                    "provider_payload": {"operation": "apply-2"},
                    "compensation": {"operation": "undo-2"},
                },
            ],
        )

    assert repo.workflows[-1].status == WorkflowStatus.RESTORED
    assert remediation.requests[-1].provider_payload == {"operation": "undo-1"}


async def _token(value: str) -> str:
    return value


@pytest.mark.asyncio
async def test_graph_provider_dry_run_never_calls_network() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Dry run must not call the provider")

    provider = GraphAccessProvider(
        httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    action = RemediationAction(
        id="action-1",
        tenant_id="tenant-1",
        project_id="project-1",
        action_type=RemediationActionType.REMOVE_ROLE,
        target_identity_id="identity-1",
        requested_by="admin",
        created_at=datetime.now(UTC),
        dry_run=True,
        provider_payload={
            "method": "DELETE",
            "url": "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments/1",
        },
    )
    result = await provider.execute(action, "token")
    assert result.details["dry_run"] is True


@pytest.mark.asyncio
async def test_graph_provider_rejects_untrusted_host() -> None:
    provider = GraphAccessProvider()
    action = RemediationAction(
        id="action-1",
        tenant_id="tenant-1",
        project_id="project-1",
        action_type=RemediationActionType.REMOVE_ROLE,
        target_identity_id="identity-1",
        requested_by="admin",
        created_at=datetime.now(UTC),
        provider_payload={"method": "DELETE", "url": "https://evil.example/action"},
    )
    with pytest.raises(ProviderOperationError) as exc_info:
        await provider.execute(action, "token")
    assert exc_info.value.category == ProviderFailureCategory.INVALID_REQUEST


@pytest.mark.asyncio
async def test_connector_worker_resolves_secret_without_persisting_it() -> None:
    now = datetime.now(UTC)
    captured_authorization = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_authorization
        captured_authorization = request.headers.get("Authorization")
        return httpx.Response(202)

    connector = ConnectorConfig(
        id="connector-1",
        project_id="project-1",
        connector_type=ConnectorType.AZURE_DEVOPS,
        endpoint="https://dev.azure.com/example/hooks",
        secret_reference="https://vault.vault.azure.net/secrets/connector-token",
        created_at=now,
        updated_at=now,
    )
    delivery = ConnectorDelivery(
        id="delivery-1",
        project_id="project-1",
        connector_id=connector.id,
        event_type="workflow.approved",
        idempotency_key="delivery-key",
        payload={"workflow_id": "workflow-1"},
        created_at=now,
        updated_at=now,
    )
    repo = _ConnectorRepo(connector, delivery)

    async def resolve(reference: str) -> str:
        assert reference == connector.secret_reference
        return "resolved-at-runtime"

    worker = ConnectorDeliveryWorker(
        repo,
        ConnectorDispatcher(httpx.AsyncClient(transport=httpx.MockTransport(handler))),
        resolve,
    )
    result = await worker.process_due("project-1")

    assert result[0].status == "delivered"
    assert captured_authorization == "Bearer resolved-at-runtime"
    assert "resolved-at-runtime" not in result[0].model_dump_json()


@pytest.mark.asyncio
async def test_connector_dispatcher_rejects_internal_endpoint() -> None:
    now = datetime.now(UTC)
    connector = ConnectorConfig(
        id="connector-1",
        project_id="project-1",
        connector_type=ConnectorType.TEAMS,
        endpoint="https://127.0.0.1/hook",
        created_at=now,
        updated_at=now,
    )
    delivery = ConnectorDelivery(
        id="delivery-1",
        project_id="project-1",
        connector_id=connector.id,
        event_type="test",
        idempotency_key="delivery-key",
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(ConnectorDeliveryError, match="non-public"):
        await ConnectorDispatcher().deliver(connector, delivery, {})


@pytest.mark.asyncio
async def test_key_vault_resolver_rejects_non_vault_reference() -> None:
    async def token_provider(scope: str) -> str:
        raise AssertionError("Invalid references must fail before token acquisition")

    resolver = KeyVaultSecretResolver(token_provider)
    with pytest.raises(ConnectorDeliveryError, match="Key Vault"):
        await resolver.resolve("https://example.com/secrets/not-allowed")


@pytest.mark.asyncio
async def test_agent_gateway_rejects_nested_secret_payload() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Secret-bearing payload must not leave the backend")

    gateway = AgentGateway(
        Settings(
            local_mode=True,
            agent_function_app_url="http://localhost:7071",
        ),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ValueError, match="forbidden"):
        await gateway.query(
            {
                "project_id": "project-1",
                "scope": {"filters": [{"access_token": "not-allowed"}]},
            }
        )


def test_split_authorization_requires_distinct_ready_apps() -> None:
    configuration = AuthorizationConfiguration(
        project_id="project-1",
        mode=AuthorizationMode.SPLIT_APPLICATIONS,
        collection_client_id="reader",
        collection_credential_reference="kv://reader",
        mutation_client_id="writer",
        mutation_credential_reference="kv://writer",
        collection_permissions=[
            "AuditLog.Read.All",
            "Directory.Read.All",
            "RoleManagement.Read.Directory",
        ],
        mutation_permissions=[
            "RoleManagement.ReadWrite.Directory",
            "PrivilegedAccess.ReadWrite.AzureAD",
        ],
        updated_at=datetime.now(UTC),
        updated_by="admin",
    )
    readiness = AuthorizationReadinessService().evaluate(configuration)
    assert readiness.ready
    unsafe = configuration.model_copy(update={"mutation_client_id": "reader"})
    assert not AuthorizationReadinessService().evaluate(unsafe).ready


def test_safety_gate_requires_production_quality_metrics() -> None:
    blocked = SafetyGateEvaluator().evaluate(
        SafetyMetrics(
            lockout_count=0,
            restore_success_rate=1,
            recommendation_precision=0.94,
            audit_chain_success_rate=1,
            canary_success_rate=1,
            sample_size=100,
        )
    )
    assert not blocked.autonomous_remediation_enabled
    allowed = SafetyGateEvaluator().evaluate(
        SafetyMetrics(
            lockout_count=0,
            restore_success_rate=1,
            recommendation_precision=0.96,
            audit_chain_success_rate=1,
            canary_success_rate=1,
            sample_size=100,
        )
    )
    assert allowed.autonomous_remediation_enabled
