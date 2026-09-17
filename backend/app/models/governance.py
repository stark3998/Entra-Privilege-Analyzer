from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class GovernanceRole(StrEnum):
    POLICY_ADMIN = "PolicyAdmin"
    REMEDIATION_APPROVER = "RemediationApprover"
    ACCESS_OWNER = "AccessOwner"
    AUDITOR = "Auditor"
    EMERGENCY_OPERATOR = "EmergencyOperator"


class AuthorizationMode(StrEnum):
    SPLIT_APPLICATIONS = "split_applications"
    COMBINED_APPLICATION = "combined_application"
    DELEGATED_OBO = "delegated_obo"


class AuthorizationConfiguration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = "authorization"
    project_id: str
    mode: AuthorizationMode = AuthorizationMode.SPLIT_APPLICATIONS
    collection_client_id: str | None = None
    collection_credential_reference: str | None = None
    mutation_client_id: str | None = None
    mutation_credential_reference: str | None = None
    delegated_scopes: list[str] = Field(default_factory=list)
    collection_permissions: list[str] = Field(default_factory=list)
    mutation_permissions: list[str] = Field(default_factory=list)
    credential_expires_at: datetime | None = None
    updated_at: datetime
    updated_by: str


class AuthorizationReadiness(BaseModel):
    mode: AuthorizationMode
    ready: bool
    collection_ready: bool
    mutation_ready: bool
    delegated_ready: bool
    missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_at: datetime


class ApprovalPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = "default"
    project_id: str
    authorization_mode: AuthorizationMode = AuthorizationMode.SPLIT_APPLICATIONS
    autonomous_max_impact: float = Field(default=25.0, ge=0.0, le=100.0)
    autonomous_min_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    autonomous_role_tiers: list[str] = Field(default_factory=lambda: ["low"])
    high_impact_threshold: float = Field(default=60.0, ge=0.0, le=100.0)
    required_human_approvals: int = Field(default=1, ge=1)
    break_glass_identity_ids: list[str] = Field(default_factory=list)
    last_global_admin_protection: bool = True
    require_access_owner: bool = False
    created_at: datetime
    updated_at: datetime
    updated_by: str


class ScoreComponent(BaseModel):
    name: str
    value: float = Field(ge=0.0, le=100.0)
    weight: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    identity_id: str
    scorecard_version: str
    risk: float = Field(ge=0.0, le=100.0)
    impact: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    components: list[ScoreComponent] = Field(default_factory=list)
    peer_group_id: str | None = None
    seasonal_anomaly: bool = False
    computed_at: datetime


class PersonaStatus(StrEnum):
    DRAFT = "draft"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class PersonaRole(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    name: str
    version: int = Field(default=1, ge=1)
    status: PersonaStatus = PersonaStatus.DRAFT
    member_identity_ids: list[str] = Field(default_factory=list)
    common_permissions: list[str] = Field(default_factory=list)
    justified_rare_permissions: list[str] = Field(default_factory=list)
    builtin_role_id: str | None = None
    builtin_role_name: str | None = None
    custom_role_definition: dict[str, Any] | None = None
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    escalation_findings: list[str] = Field(default_factory=list)
    sod_findings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    approved_by: str | None = None


class WorkflowKind(StrEnum):
    LEAST_PRIVILEGE_MIGRATION = "least_privilege_migration"
    CONTINUOUS_DRIFT = "continuous_drift"
    JIT_ACCESS = "jit_access"
    INCIDENT_CONTAINMENT = "incident_containment"
    ACCESS_REVIEW = "access_review"
    RESTORE = "restore"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    CANARY = "canary"
    GRACE_PERIOD = "grace_period"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    RESTORED = "restored"
    CANCELLED = "cancelled"


class WorkflowStep(BaseModel):
    id: str
    name: str
    status: str = "pending"
    action_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class GovernanceWorkflow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    project_id: str
    identity_id: str
    kind: WorkflowKind
    status: WorkflowStatus = WorkflowStatus.DRAFT
    correlation_id: str
    idempotency_key: str
    requested_by: str
    persona_id: str | None = None
    risk_assessment_id: str | None = None
    snapshot_id: str | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    completed_action_ids: list[str] = Field(default_factory=list)
    policy_decision: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    next_wake_at: datetime | None = None
    error: str | None = None


class AccessEdgeSnapshot(BaseModel):
    id: str
    principal_id: str
    entitlement_id: str
    edge_type: str
    scope_id: str | None = None
    assignment_id: str | None = None
    source: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    condition: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class AccessSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    project_id: str
    identity_id: str
    workflow_id: str
    encrypted_payload: str
    payload_hash: str
    edge_count: int = Field(ge=0)
    created_at: datetime
    created_by: str
    legal_hold: bool = False
    retention_until: datetime | None = None
    schema_version: int = 1


class RestoreConflict(BaseModel):
    edge_id: str
    reason: str
    snapshot_edge: AccessEdgeSnapshot | None = None
    current_edge: AccessEdgeSnapshot | None = None


class RestorePlan(BaseModel):
    snapshot_id: str
    workflow_id: str
    restore_edges: list[AccessEdgeSnapshot] = Field(default_factory=list)
    preserve_edges: list[AccessEdgeSnapshot] = Field(default_factory=list)
    conflicts: list[RestoreConflict] = Field(default_factory=list)
    requires_approval: bool = False
    generated_at: datetime


class ConnectorType(StrEnum):
    SERVICE_NOW = "servicenow"
    TEAMS = "teams"
    AZURE_DEVOPS = "azure_devops"


class ConnectorConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    project_id: str
    connector_type: ConnectorType
    endpoint: str
    enabled: bool = True
    secret_reference: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ConnectorDelivery(BaseModel):
    id: str
    project_id: str
    connector_id: str
    event_type: str
    idempotency_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "delivered", "failed", "dead_letter"] = "pending"
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class SafetyMetrics(BaseModel):
    lockout_count: int = Field(default=0, ge=0)
    restore_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation_precision: float = Field(default=0.0, ge=0.0, le=1.0)
    audit_chain_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    canary_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    approval_p95_minutes: float = Field(default=0.0, ge=0.0)
    sample_size: int = Field(default=0, ge=0)


class SafetyGateDecision(BaseModel):
    autonomous_remediation_enabled: bool
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime
