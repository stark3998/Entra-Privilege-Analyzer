from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

FUNCTIONS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_ROOT))

from agents.errors import AgentToolPolicyError  # noqa: E402
from agents.models import (  # noqa: E402
    AgentRole,
    AgentStageResult,
    CriticDisposition,
    FindingSeverity,
    InvestigatorOutput,
    PersonaOutput,
    PlannerOutput,
    PrivilegeAnalysisRequest,
    ReleaseReadiness,
    RiskOutput,
    VerifierOutput,
    WorkflowRunStatus,
)
from agents.routing import ModelRouter  # noqa: E402
from agents.runtime import AgentWorkflowRunner  # noqa: E402
from agents.tools import WorkflowEvidenceTools  # noqa: E402
from blueprints.agent_workflows_bp import (  # noqa: E402
    _orchestrate_privilege_analysis_impl,
    run_agent_step_activity,
    validate_agent_workflow_payload,
)


def _workflow_payload() -> dict:
    return {
        "workflow_id": "wf-123",
        "correlation_id": "corr-123",
        "tenant_id": "tenant-1",
        "project_id": "project-1",
        "requested_by": "analyst@example.com",
        "analysis_goal": "Validate least-privilege access for a high-risk identity.",
        "subject": {
            "identity_id": "User-user-1",
            "display_name": "User One",
            "identity_type": "User",
            "upn": "user1@example.com",
        },
        "current_roles": [
            {
                "role_id": "role-1",
                "role_name": "Global Administrator",
                "scope": "/",
                "assignment_type": "direct",
                "is_permanent": True,
            }
        ],
        "eligible_roles": [
            {
                "role_id": "role-2",
                "role_name": "Privileged Role Administrator",
                "scope": "/",
                "assignment_type": "pim_eligible",
                "is_permanent": False,
            }
        ],
        "observed_actions": [
            {
                "action": "Update user properties",
                "resource": "Users",
                "count": 4,
                "first_seen": "2026-09-01T00:00:00Z",
                "last_seen": "2026-09-14T00:00:00Z",
            }
        ],
        "risk_signals": [
            {
                "signal_id": "risk-1",
                "category": "identity_protection",
                "severity": "high",
                "summary": "Confirmed risky sign-in detected",
                "confidence": 0.9,
            }
        ],
        "persona_candidates": [
            {
                "name": "human:helpdesk",
                "match_score": 0.42,
                "common_permissions": ["User.Read.All"],
                "justified_rare_permissions": ["Group.Read.All"],
                "builtin_role_name": "User Administrator",
            }
        ],
        "permission_hints": ["User.ReadWrite.All"],
        "governance_constraints": ["Do not remove final break-glass path."],
        "additional_context": ["Identity supports overnight incident response."],
        "evidence_window_days": 45,
    }


def _success_response(role: AgentRole) -> dict:
    now = datetime.now(UTC)
    base = {
        "role": role.value,
        "prompt": {
            "name": f"prompt-{role.value}",
            "version": "2026-09-15.1",
            "checksum": "deadbeefcafebabe",
            "description": "desc",
        },
        "model_route": {
            "provider": "foundry",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 1000,
            "verbosity": "low",
        },
        "tool_policy": {"mode": "read_only", "allowlist": ["get_subject_summary"]},
        "correlation": {
            "correlation_id": "corr-123",
            "workflow_id": "wf-123",
            "tenant_id": "tenant-1",
            "project_id": "project-1",
            "trace_id": None,
            "span_id": None,
            "durable_instance_id": "wf-123",
        },
        "output_model": "OutputModel",
        "started_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "response_id": "resp-1",
        "finish_reason": "stop",
        "usage": {},
    }
    if role == AgentRole.INVESTIGATOR:
        output = InvestigatorOutput(
            summary="Identity has standing admin access and risky activity.",
            findings=[
                {
                    "id": "f1",
                    "title": "Permanent admin role",
                    "severity": FindingSeverity.CRITICAL,
                    "summary": "Global Administrator is permanently assigned.",
                    "evidence": [
                        {
                            "evidence_id": "role:role-1:/",
                            "source": "list_roles",
                            "rationale": "Current role evidence",
                        }
                    ],
                }
            ],
            recommended_focus_permissions=["User.ReadWrite.All"],
            unanswered_questions=[],
        )
    elif role == AgentRole.RISK:
        output = RiskOutput(
            overall_risk=92,
            impact=87,
            confidence=0.84,
            findings=[],
            approval_recommendation="manual_review",
        )
    elif role == AgentRole.PERSONA:
        output = PersonaOutput(
            matched_persona="human:helpdesk",
            alignment_score=0.42,
            deviation_findings=[],
            least_privilege_permissions=["User.Read.All"],
        )
    elif role == AgentRole.CRITIC:
        output = {
            "disposition": CriticDisposition.APPROVE,
            "challenge_summary": "Outputs are grounded.",
            "unsupported_claims": [],
            "missing_evidence": [],
            "required_corrections": [],
        }
    elif role == AgentRole.PLANNER:
        output = PlannerOutput(
            summary="Replace standing admin role with scoped access.",
            steps=[
                {
                    "order": 1,
                    "title": "Review standing admin assignment",
                    "rationale": "Standing GA is high-risk.",
                    "target": "Global Administrator role",
                    "validation": "Confirm helpdesk persona permissions are sufficient.",
                }
            ],
            rollback_plan=["Reinstate prior assignment if critical workflow breaks."],
            validation_checks=["Validate sign-in and helpdesk workflows after change."],
        )
    else:
        output = VerifierOutput(
            verified=True,
            summary="Plan is sufficiently grounded.",
            blocking_issues=[],
            residual_risks=["Emergency access dependence remains."],
            release_readiness=ReleaseReadiness.READY,
        )

    payload = {
        "succeeded": True,
        "result": {
            **base,
            "output": output.model_dump(mode="json")
            if hasattr(output, "model_dump")
            else output,
        },
        "failure": None,
    }
    return payload


def test_validate_agent_workflow_payload_rejects_secrets() -> None:
    payload = _workflow_payload()
    payload["client_secret"] = "forbidden"

    error = validate_agent_workflow_payload(payload)

    assert error is not None
    assert "must not be included" in error


def test_validate_agent_workflow_payload_rejects_nested_secrets() -> None:
    payload = _workflow_payload()
    payload["subject"]["access_token"] = "forbidden"

    error = validate_agent_workflow_payload(payload)

    assert error is not None
    assert "access_token" in error


def test_model_router_prefers_explicit_override() -> None:
    router = ModelRouter(
        {
            "AGENT_WORKFLOW_PROVIDER": "foundry",
            "AGENT_WORKFLOW_MODEL_DEFAULT": "default-model",
            "AGENT_WORKFLOW_MODEL_RISK": "risk-model",
        }
    )

    risk_route = router.resolve(AgentRole.RISK)
    planner_route = router.resolve(AgentRole.PLANNER, override_model="planner-override")

    assert risk_route.model == "risk-model"
    assert planner_route.model == "planner-override"
    assert planner_route.provider == "foundry"


def test_read_only_tool_allowlist_is_enforced() -> None:
    workflow = PrivilegeAnalysisRequest.model_validate(_workflow_payload())
    tools = WorkflowEvidenceTools(workflow)

    with pytest.raises(AgentToolPolicyError, match="Unknown or unauthorized"):
        tools.materialize(("not_a_tool",))


def test_runner_parses_structured_agent_output() -> None:
    runner = AgentWorkflowRunner(client_factory=lambda _route: object())
    parsed = runner._parse_output(
        type(
            "Resp",
            (),
            {
                "value": {
                    "summary": "ok",
                    "findings": [],
                    "recommended_focus_permissions": [],
                    "unanswered_questions": [],
                },
                "text": None,
            },
        )(),
        InvestigatorOutput,
    )

    assert isinstance(parsed, InvestigatorOutput)
    assert parsed.summary == "ok"


def test_run_agent_step_activity_returns_failure_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_payload: dict) -> AgentStageResult:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr("blueprints.agent_workflows_bp.run_agent_step_sync", _boom)

    response = run_agent_step_activity(
        {
            "role": AgentRole.RISK.value,
            "workflow": _workflow_payload(),
            "stage_input": {},
            "durable_instance_id": "wf-123",
        }
    )

    assert response["succeeded"] is False
    assert response["failure"]["stage"] == AgentRole.RISK.value
    assert response["failure"]["message"] == "Agent activity failed unexpectedly"


class _FakeContext:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.instance_id = payload["workflow_id"]
        self.current_utc_datetime = datetime(2026, 9, 15, tzinfo=UTC)
        self.status_updates: list[dict] = []

    def get_input(self) -> dict:
        return self._payload

    def set_custom_status(self, value: dict) -> None:
        self.status_updates.append(value)

    def call_activity_with_retry(self, name: str, _retry_options, payload: dict):
        return ("activity", name, payload)

    def task_all(self, tasks: list[tuple]):
        return ("task_all", tasks)


def test_orchestrate_privilege_analysis_happy_path() -> None:
    context = _FakeContext(_workflow_payload())
    orchestrator = _orchestrate_privilege_analysis_impl(context)

    first = next(orchestrator)
    assert first[1] == "run_agent_step_activity"
    assert first[2]["role"] == AgentRole.INVESTIGATOR.value

    second = orchestrator.send(_success_response(AgentRole.INVESTIGATOR))
    assert second[0] == "task_all"

    third = orchestrator.send(
        [
            _success_response(AgentRole.RISK),
            _success_response(AgentRole.PERSONA),
        ]
    )
    assert third[1] == "run_agent_step_activity"
    assert third[2]["role"] == AgentRole.CRITIC.value

    fourth = orchestrator.send(_success_response(AgentRole.CRITIC))
    assert fourth[2]["role"] == AgentRole.PLANNER.value

    fifth = orchestrator.send(_success_response(AgentRole.PLANNER))
    assert fifth[2]["role"] == AgentRole.VERIFIER.value

    with pytest.raises(StopIteration) as stop:
        orchestrator.send(_success_response(AgentRole.VERIFIER))

    result = stop.value.value
    assert result["status"] == WorkflowRunStatus.COMPLETED.value
    assert [step["role"] for step in result["steps"]] == [
        AgentRole.INVESTIGATOR.value,
        AgentRole.RISK.value,
        AgentRole.PERSONA.value,
        AgentRole.CRITIC.value,
        AgentRole.PLANNER.value,
        AgentRole.VERIFIER.value,
    ]


def test_orchestrate_privilege_analysis_fails_closed() -> None:
    context = _FakeContext(_workflow_payload())
    orchestrator = _orchestrate_privilege_analysis_impl(context)
    next(orchestrator)
    parallel = orchestrator.send(_success_response(AgentRole.INVESTIGATOR))
    assert parallel[0] == "task_all"

    with pytest.raises(StopIteration) as stop:
        orchestrator.send(
            [
                {
                    "succeeded": False,
                    "result": None,
                    "failure": {
                        "stage": AgentRole.RISK.value,
                        "message": "structured output invalid",
                    },
                },
                _success_response(AgentRole.PERSONA),
            ]
        )

    result = stop.value.value
    assert result["status"] == WorkflowRunStatus.FAILED.value
    assert result["failure"]["stage"] == AgentRole.RISK.value
