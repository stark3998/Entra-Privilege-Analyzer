from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from azure.identity.aio import DefaultAzureCredential
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.auth.deps import CurrentUser, get_current_user, validate_project_access
from app.config import Settings, get_settings
from app.models.governance import (
    AccessEdgeSnapshot,
    ApprovalPolicy,
    AuthorizationConfiguration,
    AuthorizationMode,
    ConnectorConfig,
    ConnectorDelivery,
    ConnectorType,
    PersonaStatus,
    SafetyMetrics,
    WorkflowKind,
    WorkflowStatus,
)
from app.models.tenant_evidence import TenantRegistryEntry
from app.services.agent_gateway import AgentGateway
from app.services.authorization_governance import AuthorizationGovernanceService
from app.services.authorization_readiness import AuthorizationReadinessService
from app.services.connectors import (
    ConnectorDeliveryWorker,
    ConnectorDispatcher,
    KeyVaultSecretResolver,
)
from app.services.crypto import CryptoService
from app.services.evidence_migration import ProjectEvidenceMigrator
from app.services.follow_on_workflows import create_follow_on_workflow
from app.services.governance_repo import GovernanceRepo
from app.services.governance_workflow import GovernanceWorkflowService
from app.services.master_repo import MasterRepo, get_master_repo
from app.services.persona_lifecycle import PersonaLifecycleService
from app.services.project_repo import ProjectRepo
from app.services.project_repo_cache import ProjectRepoCache
from app.services.risk_confidence_engine import RiskConfidenceEngine
from app.services.role_mapper import RoleMapper
from app.services.safety_gates import SafetyGateEvaluator
from app.services.snapshot_restore import SnapshotRestoreService
from app.services.tenant_evidence_db_manager import TenantEvidenceDatabaseManager
from app.services.tenant_evidence_repo import TenantEvidenceRepo
from app.services.tenant_evidence_repo_cache import TenantEvidenceRepoCache

router = APIRouter(prefix="/api/projects/{project_id}/governance", tags=["governance"])
_authorization = AuthorizationGovernanceService()


class PolicyPayload(BaseModel):
    authorization_mode: AuthorizationMode = AuthorizationMode.SPLIT_APPLICATIONS
    autonomous_max_impact: float = Field(default=25.0, ge=0.0, le=100.0)
    autonomous_min_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    autonomous_role_tiers: list[str] = Field(default_factory=lambda: ["low"])
    high_impact_threshold: float = Field(default=60.0, ge=0.0, le=100.0)
    required_human_approvals: int = Field(default=1, ge=1)
    break_glass_identity_ids: list[str] = Field(default_factory=list)
    last_global_admin_protection: bool = True
    require_access_owner: bool = False


class AuthorizationPayload(BaseModel):
    mode: AuthorizationMode = AuthorizationMode.SPLIT_APPLICATIONS
    collection_client_id: str | None = None
    collection_credential_reference: str | None = None
    mutation_client_id: str | None = None
    mutation_credential_reference: str | None = None
    delegated_scopes: list[str] = Field(default_factory=list)
    collection_permissions: list[str] = Field(default_factory=list)
    mutation_permissions: list[str] = Field(default_factory=list)
    credential_expires_at: datetime | None = None


class RiskPayload(BaseModel):
    identity_id: str
    drift_score: float = Field(ge=0.0, le=100.0)
    unused_permission_ratio: float = Field(ge=0.0, le=1.0)
    peer_deviation: float = Field(ge=0.0, le=100.0)
    seasonal_deviation: float = Field(ge=0.0, le=100.0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    evidence_days: int = Field(ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class PersonaPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    identity_ids: list[str] = Field(min_length=2)


class WorkflowPayload(BaseModel):
    kind: WorkflowKind = WorkflowKind.LEAST_PRIVILEGE_MIGRATION
    identity_id: str
    idempotency_key: str = Field(min_length=1, max_length=200)
    persona_id: str | None = None
    risk_assessment_id: str | None = None


class SnapshotPayload(BaseModel):
    workflow_id: str
    identity_id: str
    edges: list[AccessEdgeSnapshot]
    retention_days: int = Field(default=365, ge=1, le=3650)
    legal_hold: bool = False


class RestorePayload(BaseModel):
    identity_id: str
    current_edges: list[AccessEdgeSnapshot]
    workflow_mutated_edge_ids: set[str] = Field(default_factory=set)


class ConnectorPayload(BaseModel):
    connector_type: ConnectorType
    endpoint: str
    secret_reference: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Connector endpoint must use HTTPS")
        return value

    @field_validator("secret_reference")
    @classmethod
    def validate_secret_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".vault.azure.net")
            or not parsed.path.startswith("/secrets/")
        ):
            raise ValueError("secret_reference must be an Azure Key Vault secret URI")
        return value

    @field_validator("settings")
    @classmethod
    def reject_inline_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = {
            key
            for key in _nested_keys(value)
            if any(part in key.lower() for part in ("secret", "token", "password", "key"))
            and key != "secret_usage"
        }
        if forbidden:
            raise ValueError(
                "Connector settings contain secret-bearing fields: "
                + ", ".join(sorted(forbidden))
            )
        return value


class ConnectorDeliveryPayload(BaseModel):
    event_type: str = Field(min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def reject_inline_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = {
            key
            for key in _nested_keys(value)
            if any(
                part in key.lower()
                for part in ("secret", "token", "password", "connection_string")
            )
        }
        if forbidden:
            raise ValueError(
                "Connector payload contains secret-bearing fields: "
                + ", ".join(sorted(forbidden))
            )
        return value


class CopilotQueryPayload(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    scope: dict[str, Any] = Field(default_factory=dict)


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            key
            for item_key, item_value in value.items()
            for key in ({str(item_key)} | _nested_keys(item_value))
        }
    if isinstance(value, list):
        return {key for item in value for key in _nested_keys(item)}
    return set()


async def _context(
    project_id: str,
    user: CurrentUser,
    master: MasterRepo,
    request: Request,
    settings: Settings,
    capability: str,
) -> tuple[str, ProjectRepo, TenantEvidenceRepo, GovernanceRepo]:
    try:
        _authorization.require_capability(user.roles, capability)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    project = await validate_project_access(project_id, user, master, settings)
    project_cache: ProjectRepoCache | None = request.app.state.project_repo_cache
    tenant_cache: TenantEvidenceRepoCache | None = request.app.state.tenant_evidence_repo_cache
    if project_cache is None or tenant_cache is None or not project.database_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Evidence repositories are not available",
        )
    registry = await master.get_tenant_registry_entry(project.target_tenant_id)
    if registry is None:
        cosmos_client = request.app.state.cosmos_client
        if cosmos_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tenant evidence database is not provisioned",
            )
        manager = TenantEvidenceDatabaseManager(
            cosmos_client,
            settings.tenant_evidence_raw_ttl_seconds,
        )
        database_name = await manager.provision_tenant_database(
            project.target_tenant_id
        )
        now = datetime.now(UTC)
        await master.register_tenant_project(
            TenantRegistryEntry(
                id=project.target_tenant_id,
                display_name=project.target_tenant_name,
                database_name=database_name,
                status="active",
                project_ids=[project.id],
                raw_activity_retention_days=(
                    settings.tenant_evidence_raw_ttl_seconds // 86400
                ),
                created_at=now,
                updated_at=now,
            ),
            project.id,
        )
    project_repo = await project_cache.get_repo(project.database_name)
    tenant_repo = await tenant_cache.get_repo(project.target_tenant_id)
    return (
        project.target_tenant_id,
        project_repo,
        tenant_repo,
        GovernanceRepo(project_repo.database),
    )


@router.get("/evidence/health")
async def evidence_health(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, tenant_repo, _ = await _context(
        project_id, user, master, request, settings, "evidence.read"
    )
    quality = await tenant_repo.list_data_quality(tenant_id)
    return {
        "tenant_id": tenant_id,
        "sources": [item.model_dump(mode="json") for item in quality],
        "complete": bool(quality) and all(item.completeness >= 0.9 for item in quality),
    }


@router.get("/evidence/identities/{identity_id}/access")
async def effective_access(
    project_id: str,
    identity_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, tenant_repo, _ = await _context(
        project_id, user, master, request, settings, "evidence.read"
    )
    edges = await tenant_repo.list_entitlement_edges(identity_id)
    return {
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "items": [edge.model_dump(mode="json") for edge in edges],
    }


@router.post("/evidence/migrate")
async def migrate_evidence(
    project_id: str,
    scan_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, int]:
    tenant_id, project_repo, tenant_repo, _ = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    return await ProjectEvidenceMigrator(project_repo, tenant_repo).migrate(
        tenant_id, project_id, scan_id
    )


@router.put("/evidence/legal-hold")
async def set_legal_hold(
    project_id: str,
    enabled: bool,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, _, _ = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    entry = await master.set_tenant_legal_hold(tenant_id, enabled, datetime.now(UTC))
    return entry.model_dump(mode="json")


@router.post("/risk-assessments")
async def create_risk_assessment(
    project_id: str,
    payload: RiskPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, project_repo, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.request"
    )
    identity = await project_repo.get_identity(payload.identity_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Identity not found")
    assessment = RiskConfidenceEngine().assess(
        identity,
        drift_score=payload.drift_score,
        unused_permission_ratio=payload.unused_permission_ratio,
        peer_deviation=payload.peer_deviation,
        seasonal_deviation=payload.seasonal_deviation,
        evidence_coverage=payload.evidence_coverage,
        evidence_days=payload.evidence_days,
        evidence_ids=payload.evidence_ids,
    )
    saved = await governance_repo.upsert_risk_assessment(assessment)
    return saved.model_dump(mode="json")


@router.get("/personas")
async def list_personas(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    tenant_id, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "evidence.read"
    )
    return [
        item.model_dump(mode="json")
        for item in await governance_repo.list_personas(tenant_id)
    ]


@router.post("/personas", status_code=status.HTTP_201_CREATED)
async def create_persona(
    project_id: str,
    payload: PersonaPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, project_repo, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    identities = []
    for identity_id in payload.identity_ids:
        identity = await project_repo.get_identity(identity_id)
        if identity is None:
            raise HTTPException(status_code=404, detail=f"Identity {identity_id} not found")
        identities.append(identity)
    persona = PersonaLifecycleService(RoleMapper()).build_persona(
        tenant_id, payload.name, identities
    )
    return (await governance_repo.upsert_persona(persona)).model_dump(mode="json")


@router.post("/personas/{persona_id}/status")
async def transition_persona(
    project_id: str,
    persona_id: str,
    target: PersonaStatus,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    personas = await governance_repo.list_personas(tenant_id)
    persona = next((item for item in personas if item.id == persona_id), None)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    updated = PersonaLifecycleService(RoleMapper()).transition(persona, target, user.oid)
    return (await governance_repo.upsert_persona(updated)).model_dump(mode="json")


@router.get("/policy")
async def get_policy(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any] | None:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.read"
    )
    policy = await governance_repo.get_policy(project_id)
    return policy.model_dump(mode="json") if policy else None


@router.get("/authorization/readiness")
async def authorization_readiness(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.read"
    )
    configuration = await governance_repo.get_authorization(project_id)
    if configuration is None:
        raise HTTPException(status_code=404, detail="Authorization is not configured")
    return AuthorizationReadinessService().evaluate(configuration).model_dump(mode="json")


@router.put("/authorization")
async def put_authorization(
    project_id: str,
    payload: AuthorizationPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    configuration = AuthorizationConfiguration(
        id="authorization",
        project_id=project_id,
        updated_at=datetime.now(UTC),
        updated_by=user.oid,
        **payload.model_dump(),
    )
    saved = await governance_repo.upsert_authorization(configuration)
    return {
        "configuration": saved.model_dump(mode="json"),
        "readiness": AuthorizationReadinessService()
        .evaluate(saved)
        .model_dump(mode="json"),
    }


@router.post("/safety-gates/evaluate")
async def evaluate_safety_gates(
    project_id: str,
    payload: SafetyMetrics,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    await _context(project_id, user, master, request, settings, "policy.write")
    return SafetyGateEvaluator().evaluate(payload).model_dump(mode="json")


@router.put("/policy")
async def put_policy(
    project_id: str,
    payload: PolicyPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    now = datetime.now(UTC)
    existing = await governance_repo.get_policy(project_id)
    policy = ApprovalPolicy(
        id="default",
        project_id=project_id,
        created_at=existing.created_at if existing else now,
        updated_at=now,
        updated_by=user.oid,
        **payload.model_dump(),
    )
    return (await governance_repo.upsert_policy(policy)).model_dump(mode="json")


@router.get("/workflows")
async def list_workflows(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.read"
    )
    return [
        item.model_dump(mode="json")
        for item in await governance_repo.list_workflows(project_id)
    ]


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    project_id: str,
    payload: WorkflowPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.request"
    )
    existing = await governance_repo.find_workflow_by_idempotency_key(
        project_id, payload.idempotency_key
    )
    if existing:
        if existing.identity_id != payload.identity_id or existing.kind != payload.kind:
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        return existing.model_dump(mode="json")
    if payload.kind == WorkflowKind.LEAST_PRIVILEGE_MIGRATION:
        workflow = GovernanceWorkflowService(_authorization).create_migration(
            tenant_id=tenant_id,
            project_id=project_id,
            identity_id=payload.identity_id,
            requested_by=user.oid,
            idempotency_key=payload.idempotency_key,
            persona_id=payload.persona_id,
            risk_assessment_id=payload.risk_assessment_id,
        )
    else:
        workflow = create_follow_on_workflow(
            kind=payload.kind,
            tenant_id=tenant_id,
            project_id=project_id,
            identity_id=payload.identity_id,
            requested_by=user.oid,
            idempotency_key=payload.idempotency_key,
        )
    return (await governance_repo.upsert_workflow(workflow)).model_dump(mode="json")


@router.post("/workflows/{workflow_id}/approve")
async def approve_workflow(
    project_id: str,
    workflow_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.approve"
    )
    workflow = await governance_repo.find_workflow(workflow_id)
    if workflow is None or workflow.project_id != project_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    policy = await governance_repo.get_policy(project_id)
    if policy is None:
        raise HTTPException(status_code=409, detail="Approval policy is not configured")
    try:
        updated = GovernanceWorkflowService(_authorization).approve(
            workflow,
            approver_id=user.oid,
            approver_roles=user.roles,
            policy=policy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return (await governance_repo.upsert_workflow(updated)).model_dump(mode="json")


@router.post("/workflows/{workflow_id}/transition")
async def transition_workflow(
    project_id: str,
    workflow_id: str,
    target: WorkflowStatus,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.request"
    )
    workflow = await governance_repo.find_workflow(workflow_id)
    if workflow is None or workflow.project_id != project_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        updated = GovernanceWorkflowService(_authorization).transition(workflow, target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return (await governance_repo.upsert_workflow(updated)).model_dump(mode="json")


@router.post("/snapshots", status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    project_id: str,
    payload: SnapshotPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.request"
    )
    snapshot = SnapshotRestoreService(CryptoService(settings)).create_snapshot(
        tenant_id=tenant_id,
        project_id=project_id,
        identity_id=payload.identity_id,
        workflow_id=payload.workflow_id,
        edges=payload.edges,
        created_by=user.oid,
        retention_days=payload.retention_days,
        legal_hold=payload.legal_hold,
    )
    return (await governance_repo.upsert_snapshot(snapshot)).model_dump(mode="json")


@router.post("/snapshots/{snapshot_id}/restore-plan")
async def create_restore_plan(
    project_id: str,
    snapshot_id: str,
    payload: RestorePayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "restore.execute"
    )
    snapshot = await governance_repo.get_snapshot(snapshot_id, payload.identity_id)
    if snapshot is None or snapshot.project_id != project_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    plan = SnapshotRestoreService(CryptoService(settings)).build_restore_plan(
        snapshot,
        payload.current_edges,
        payload.workflow_mutated_edge_ids,
    )
    return plan.model_dump(mode="json")


@router.get("/connectors")
async def list_connectors(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.read"
    )
    return [
        item.model_dump(mode="json")
        for item in await governance_repo.list_connectors(project_id)
    ]


@router.post("/connectors", status_code=status.HTTP_201_CREATED)
async def create_connector(
    project_id: str,
    payload: ConnectorPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "policy.write"
    )
    now = datetime.now(UTC)
    connector = ConnectorConfig(
        id=str(uuid.uuid4()),
        project_id=project_id,
        created_at=now,
        updated_at=now,
        **payload.model_dump(),
    )
    return (await governance_repo.upsert_connector(connector)).model_dump(mode="json")


@router.post("/connectors/{connector_id}/deliveries", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_connector_delivery(
    project_id: str,
    connector_id: str,
    payload: ConnectorDeliveryPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _, _, _, governance_repo = await _context(
        project_id, user, master, request, settings, "workflow.request"
    )
    connector = await governance_repo.get_connector(connector_id, project_id)
    if connector is None or not connector.enabled:
        raise HTTPException(status_code=404, detail="Enabled connector not found")
    existing = await governance_repo.find_delivery_by_idempotency_key(
        project_id,
        payload.idempotency_key,
    )
    if existing:
        return existing.model_dump(mode="json")
    now = datetime.now(UTC)
    delivery = ConnectorDelivery(
        id=str(uuid.uuid4()),
        project_id=project_id,
        connector_id=connector_id,
        event_type=payload.event_type,
        idempotency_key=payload.idempotency_key,
        payload=payload.payload,
        created_at=now,
        updated_at=now,
    )
    return (await governance_repo.upsert_delivery(delivery)).model_dump(mode="json")


@router.post("/connectors/deliveries/process")
async def process_connector_deliveries(
    project_id: str,
    request: Request,
    limit: int = 100,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    _, _, _, governance_repo = await _context(
        project_id,
        user,
        master,
        request,
        settings,
        "policy.write",
    )
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
        managed_identity_client_id=settings.managed_identity_client_id or None,
    )

    async def token_provider(scope: str) -> str:
        return (await credential.get_token(scope)).token

    try:
        deliveries = await ConnectorDeliveryWorker(
            governance_repo,
            ConnectorDispatcher(),
            KeyVaultSecretResolver(token_provider).resolve,
        ).process_due(project_id, limit=limit)
    finally:
        await credential.close()
    return [delivery.model_dump(mode="json") for delivery in deliveries]


@router.post("/copilot/query")
async def query_governance_copilot(
    project_id: str,
    payload: CopilotQueryPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    master: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tenant_id, _, _, _ = await _context(
        project_id, user, master, request, settings, "evidence.read"
    )
    try:
        gateway = AgentGateway(settings)
        return await gateway.query(
            {
                "project_id": project_id,
                "tenant_id": tenant_id,
                "user_id": user.oid,
                "query": payload.query,
                "scope": payload.scope,
                "correlation_id": request.headers.get("x-request-id", str(uuid.uuid4())),
            }
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
