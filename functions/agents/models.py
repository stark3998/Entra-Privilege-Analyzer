"""Pydantic contracts for Functions-hosted durable agent workflows."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentRole(StrEnum):
    INVESTIGATOR = "investigator"
    RISK = "risk"
    PERSONA = "persona"
    CRITIC = "critic"
    PLANNER = "planner"
    VERIFIER = "verifier"


class FindingSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CriticDisposition(StrEnum):
    APPROVE = "approve"
    REVISE = "revise"


class ReleaseReadiness(StrEnum):
    READY = "ready"
    NEEDS_REVISION = "needs_revision"


class WorkflowRunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowSubject(StrictModel):
    identity_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    identity_type: str = Field(min_length=1)
    upn: str | None = None
    app_id: str | None = None


class WorkflowRoleAssignment(StrictModel):
    role_id: str = Field(min_length=1)
    role_name: str = Field(min_length=1)
    scope: str = "/"
    assignment_type: str = "direct"
    is_permanent: bool = True
    start_date: datetime | None = None
    end_date: datetime | None = None
    member_type: str = "Direct"


class WorkflowObservedAction(StrictModel):
    action: str = Field(min_length=1)
    resource: str | None = None
    count: int = Field(default=0, ge=0)
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class WorkflowRiskSignal(StrictModel):
    signal_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: FindingSeverity
    summary: str = Field(min_length=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PersonaCandidate(StrictModel):
    name: str = Field(min_length=1)
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    common_permissions: list[str] = Field(default_factory=list)
    justified_rare_permissions: list[str] = Field(default_factory=list)
    builtin_role_name: str | None = None


class PrivilegeAnalysisRequest(StrictModel):
    workflow_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    analysis_goal: str = Field(min_length=1)
    prompt_bundle_version: str = Field(default="2026-09-15.1", min_length=1)
    subject: WorkflowSubject
    current_roles: list[WorkflowRoleAssignment] = Field(default_factory=list)
    eligible_roles: list[WorkflowRoleAssignment] = Field(default_factory=list)
    observed_actions: list[WorkflowObservedAction] = Field(default_factory=list)
    risk_signals: list[WorkflowRiskSignal] = Field(default_factory=list)
    persona_candidates: list[PersonaCandidate] = Field(default_factory=list)
    permission_hints: list[str] = Field(default_factory=list)
    governance_constraints: list[str] = Field(default_factory=list)
    additional_context: list[str] = Field(default_factory=list)
    evidence_window_days: int = Field(default=30, ge=1, le=366)
    model_overrides: dict[AgentRole, str] = Field(default_factory=dict)


class EvidenceCitation(StrictModel):
    evidence_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class StructuredFinding(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    severity: FindingSeverity
    summary: str = Field(min_length=1)
    evidence: list[EvidenceCitation] = Field(default_factory=list)


class InvestigatorOutput(StrictModel):
    summary: str = Field(min_length=1)
    findings: list[StructuredFinding] = Field(default_factory=list)
    recommended_focus_permissions: list[str] = Field(default_factory=list)
    unanswered_questions: list[str] = Field(default_factory=list)


class RiskOutput(StrictModel):
    overall_risk: float = Field(ge=0.0, le=100.0)
    impact: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    findings: list[StructuredFinding] = Field(default_factory=list)
    approval_recommendation: str = Field(min_length=1)


class PersonaOutput(StrictModel):
    matched_persona: str | None = None
    alignment_score: float = Field(default=0.0, ge=0.0, le=1.0)
    deviation_findings: list[StructuredFinding] = Field(default_factory=list)
    least_privilege_permissions: list[str] = Field(default_factory=list)


class CriticOutput(StrictModel):
    disposition: CriticDisposition
    challenge_summary: str = Field(min_length=1)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    required_corrections: list[str] = Field(default_factory=list)


class PlanStep(StrictModel):
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    target: str = Field(min_length=1)
    validation: str = Field(min_length=1)


class PlannerOutput(StrictModel):
    summary: str = Field(min_length=1)
    steps: list[PlanStep] = Field(default_factory=list)
    rollback_plan: list[str] = Field(default_factory=list)
    validation_checks: list[str] = Field(default_factory=list)


class VerifierOutput(StrictModel):
    verified: bool
    summary: str = Field(min_length=1)
    blocking_issues: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    release_readiness: ReleaseReadiness


class InvestigatorStageInput(StrictModel):
    workflow: PrivilegeAnalysisRequest


class RiskStageInput(StrictModel):
    workflow: PrivilegeAnalysisRequest
    investigator: InvestigatorOutput


class PersonaStageInput(StrictModel):
    workflow: PrivilegeAnalysisRequest
    investigator: InvestigatorOutput


class CriticStageInput(StrictModel):
    workflow: PrivilegeAnalysisRequest
    investigator: InvestigatorOutput
    risk: RiskOutput
    persona: PersonaOutput


class PlannerStageInput(StrictModel):
    workflow: PrivilegeAnalysisRequest
    investigator: InvestigatorOutput
    risk: RiskOutput
    persona: PersonaOutput
    critic: CriticOutput


class VerifierStageInput(StrictModel):
    workflow: PrivilegeAnalysisRequest
    investigator: InvestigatorOutput
    risk: RiskOutput
    persona: PersonaOutput
    critic: CriticOutput
    planner: PlannerOutput


class PromptMetadata(StrictModel):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    description: str = Field(min_length=1)


class ModelRoute(StrictModel):
    provider: Literal["foundry"]
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=1, le=16384)
    verbosity: Literal["low", "medium", "high"]


class CorrelationContext(StrictModel):
    correlation_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    trace_id: str | None = None
    span_id: str | None = None
    durable_instance_id: str | None = None


class ToolPolicy(StrictModel):
    mode: Literal["read_only"] = "read_only"
    allowlist: list[str] = Field(default_factory=list)


class AgentStageResult(StrictModel):
    role: AgentRole
    prompt: PromptMetadata
    model_route: ModelRoute
    tool_policy: ToolPolicy
    correlation: CorrelationContext
    output_model: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    response_id: str | None = None
    finish_reason: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any]


class AgentWorkflowFailure(StrictModel):
    stage: AgentRole
    message: str = Field(min_length=1)


class AgentStepActivityResponse(StrictModel):
    succeeded: bool
    result: AgentStageResult | None = None
    failure: AgentWorkflowFailure | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "AgentStepActivityResponse":
        if self.succeeded:
            if self.result is None or self.failure is not None:
                raise ValueError(
                    "Successful activity responses require result and no failure"
                )
        else:
            if self.failure is None or self.result is not None:
                raise ValueError(
                    "Failed activity responses require failure and no result"
                )
        return self


class AgentWorkflowResult(StrictModel):
    workflow_id: str = Field(min_length=1)
    status: WorkflowRunStatus
    correlation: CorrelationContext
    subject_identity_id: str = Field(min_length=1)
    steps: list[AgentStageResult] = Field(default_factory=list)
    failure: AgentWorkflowFailure | None = None
    completed_at: datetime


class RunAgentStepRequest(StrictModel):
    role: AgentRole
    workflow: PrivilegeAnalysisRequest
    stage_input: dict[str, Any]
    durable_instance_id: str | None = None


class AgentQueryScope(StrictModel):
    identity_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    max_results: int = Field(default=8, ge=1, le=25)
    include_drift: bool = True
    include_recommendations: bool = True
    include_best_practices: bool = True


class AgentQueryRequest(StrictModel):
    project_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=4000)
    scope: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(min_length=1)


class QueryCitation(StrictModel):
    evidence_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    source: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)


class StructuredAnswerFinding(StrictModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class StructuredAnswer(StrictModel):
    summary: str = Field(min_length=1)
    findings: list[StructuredAnswerFinding] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AgentQueryOutput(StrictModel):
    structured_answer: StructuredAnswer
    citations: list[QueryCitation] = Field(default_factory=list)


class AgentDescriptor(StrictModel):
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    version: str = Field(min_length=1)
    prompt_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)


class QueryTrace(StrictModel):
    correlation_id: str = Field(min_length=1)
    trace_id: str | None = None
    span_id: str | None = None


class AgentQueryResponse(StrictModel):
    answer: str = Field(min_length=1)
    structured_answer: StructuredAnswer
    citations: list[QueryCitation] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    agent: AgentDescriptor
    version: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    trace: QueryTrace
