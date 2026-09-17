"""Durable Microsoft Agent Framework workflows for privilege investigations."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import azure.durable_functions as df
import azure.functions as func
from pydantic import ValidationError

from agents.errors import AgentWorkflowError
from agents.models import (
    AgentQueryScope,
    AgentQueryRequest,
    AgentRole,
    AgentStepActivityResponse,
    AgentWorkflowFailure,
    AgentWorkflowResult,
    CriticOutput,
    CriticStageInput,
    InvestigatorOutput,
    InvestigatorStageInput,
    PersonaOutput,
    PersonaStageInput,
    PlannerOutput,
    PlannerStageInput,
    PrivilegeAnalysisRequest,
    RiskOutput,
    RiskStageInput,
    VerifierOutput,
    VerifierStageInput,
    WorkflowRunStatus,
)
from agents.query_runtime import QueryAgentRunner
from agents.runtime import run_agent_step_sync
from blueprints.shared import RETRY_OPTIONS
from utils.log_context import set_agent_workflow_context

logger = logging.getLogger(__name__)

bp = df.Blueprint()

_FORBIDDEN_QUERY_FIELDS = {
    "access_token",
    "api_key",
    "client_secret",
    "connection_string",
    "cosmos_key",
    "credential",
    "encryption_key",
    "password",
    "token",
}
_QUERY_RUNNER = QueryAgentRunner()


def validate_agent_workflow_payload(body: dict[str, Any]) -> str | None:
    present_forbidden = sorted(_find_secret_bearing_fields(body))
    if present_forbidden:
        return (
            "Secrets and credentials must not be included in agent workflow input: "
            f"{', '.join(present_forbidden)}"
        )
    try:
        PrivilegeAnalysisRequest.model_validate(body)
    except ValidationError as exc:
        return str(exc)
    return None


def _find_secret_bearing_fields(value: Any) -> set[str]:
    if isinstance(value, dict):
        matches: set[str] = set()
        for key, nested in value.items():
            lowered = str(key).lower()
            if (
                lowered in _FORBIDDEN_QUERY_FIELDS
                or lowered.endswith("_secret")
                or lowered.endswith("_token")
            ):
                matches.add(str(key))
            matches.update(_find_secret_bearing_fields(nested))
        return matches
    if isinstance(value, list):
        matches: set[str] = set()
        for nested in value:
            matches.update(_find_secret_bearing_fields(nested))
        return matches
    return set()


def validate_agent_query_payload(body: dict[str, Any]) -> str | None:
    forbidden = sorted(_find_secret_bearing_fields(body))
    if forbidden:
        return (
            "Secret-bearing fields must not be included in agent query input: "
            f"{', '.join(forbidden)}"
        )
    try:
        request = AgentQueryRequest.model_validate(body)
        AgentQueryScope.model_validate(request.scope)
    except ValidationError as exc:
        return str(exc)
    return None


def _workflow_failure(
    workflow: PrivilegeAnalysisRequest,
    failure: AgentWorkflowFailure,
    successful_steps: list[dict[str, Any]],
    completed_at: datetime,
) -> dict[str, Any]:
    return AgentWorkflowResult(
        workflow_id=workflow.workflow_id,
        status=WorkflowRunStatus.FAILED,
        correlation={
            "correlation_id": workflow.correlation_id,
            "workflow_id": workflow.workflow_id,
            "tenant_id": workflow.tenant_id,
            "project_id": workflow.project_id,
            "trace_id": None,
            "span_id": None,
            "durable_instance_id": workflow.workflow_id,
        },
        subject_identity_id=workflow.subject.identity_id,
        steps=successful_steps,
        failure=failure,
        completed_at=completed_at,
    ).model_dump(mode="json")


def _normalize_workflow_input(
    req: func.HttpRequest, body: dict[str, Any]
) -> dict[str, Any]:
    if not body.get("correlation_id"):
        body = dict(body)
        body["correlation_id"] = (
            req.headers.get("x-correlation-id")
            or req.headers.get("traceparent")
            or body.get("workflow_id")
            or ""
        )
    return body


def _step_request(
    *,
    role: AgentRole,
    workflow: PrivilegeAnalysisRequest,
    stage_input: dict[str, Any],
    durable_instance_id: str,
) -> dict[str, Any]:
    return {
        "role": role.value,
        "workflow": workflow.model_dump(mode="json"),
        "stage_input": stage_input,
        "durable_instance_id": durable_instance_id,
    }


def _unwrap_activity_response(
    workflow: PrivilegeAnalysisRequest,
    raw: dict[str, Any],
    steps: list[dict[str, Any]],
    completed_at: datetime,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    response = AgentStepActivityResponse.model_validate(raw)
    if response.succeeded and response.result is not None:
        step_dict = response.result.model_dump(mode="json")
        steps.append(step_dict)
        return step_dict, None
    if response.failure is None:
        raise AgentWorkflowError("Agent activity returned neither result nor failure")
    return None, _workflow_failure(workflow, response.failure, steps, completed_at)


async def _query_agent_impl(body: dict[str, Any]):
    request = AgentQueryRequest.model_validate(body)
    return await _QUERY_RUNNER.run(request)


@bp.route(
    route="agent_workflows/start", methods=["POST"], auth_level=func.AuthLevel.FUNCTION
)
@bp.durable_client_input(client_name="client")
async def start_agent_workflow(req: func.HttpRequest, client) -> func.HttpResponse:
    """Validate input and start the privilege-analysis durable orchestration."""
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    normalized = _normalize_workflow_input(req, body)
    validation_error = validate_agent_workflow_payload(normalized)
    if validation_error:
        return func.HttpResponse(
            json.dumps({"error": validation_error}),
            status_code=400,
            mimetype="application/json",
        )

    workflow = PrivilegeAnalysisRequest.model_validate(normalized)
    instance_id = await client.start_new(
        "orchestrate_privilege_analysis",
        instance_id=workflow.workflow_id,
        client_input=workflow.model_dump(mode="json"),
    )
    return client.create_check_status_response(req, instance_id)


@bp.route(route="agent/query", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
async def query_agent(req: func.HttpRequest) -> func.HttpResponse:
    """Answer a scoped copilot query with identifier-only input."""
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json",
        )

    validation_error = validate_agent_query_payload(body)
    if validation_error:
        return func.HttpResponse(
            json.dumps({"error": validation_error}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        response = await _query_agent_impl(body)
    except AgentWorkflowError as exc:
        logger.exception(
            "query_agent FAILED | correlation=%s | error=%s",
            body.get("correlation_id"),
            exc,
        )
        return func.HttpResponse(
            json.dumps({"error": str(exc)}),
            status_code=503,
            mimetype="application/json",
        )
    except Exception as exc:
        logger.exception(
            "query_agent FAILED unexpectedly | correlation=%s | error=%s",
            body.get("correlation_id"),
            exc,
        )
        return func.HttpResponse(
            json.dumps({"error": "Agent query failed unexpectedly"}),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        response.model_dump_json(),
        status_code=200,
        mimetype="application/json",
    )


def _orchestrate_privilege_analysis_impl(context: df.DurableOrchestrationContext):
    workflow = PrivilegeAnalysisRequest.model_validate(context.get_input())
    instance_id = context.instance_id or workflow.workflow_id
    steps: list[dict[str, Any]] = []

    context.set_custom_status(
        {
            "step": AgentRole.INVESTIGATOR.value,
            "message": "Running read-only investigator agent...",
            "workflow_id": workflow.workflow_id,
        }
    )
    investigator_raw = yield context.call_activity_with_retry(
        "run_agent_step_activity",
        RETRY_OPTIONS,
        _step_request(
            role=AgentRole.INVESTIGATOR,
            workflow=workflow,
            stage_input=InvestigatorStageInput(workflow=workflow).model_dump(
                mode="json"
            ),
            durable_instance_id=instance_id,
        ),
    )
    investigator_step, failure = _unwrap_activity_response(
        workflow, investigator_raw, steps, context.current_utc_datetime
    )
    if failure:
        context.set_custom_status(
            {"step": "failed", "message": failure["failure"]["message"]}
        )
        return failure
    investigator = InvestigatorOutput.model_validate(investigator_step["output"])

    context.set_custom_status(
        {
            "step": "risk_persona",
            "message": "Running risk and persona agents in parallel...",
            "workflow_id": workflow.workflow_id,
        }
    )
    risk_and_persona = yield context.task_all(
        [
            context.call_activity_with_retry(
                "run_agent_step_activity",
                RETRY_OPTIONS,
                _step_request(
                    role=AgentRole.RISK,
                    workflow=workflow,
                    stage_input=RiskStageInput(
                        workflow=workflow,
                        investigator=investigator,
                    ).model_dump(mode="json"),
                    durable_instance_id=instance_id,
                ),
            ),
            context.call_activity_with_retry(
                "run_agent_step_activity",
                RETRY_OPTIONS,
                _step_request(
                    role=AgentRole.PERSONA,
                    workflow=workflow,
                    stage_input=PersonaStageInput(
                        workflow=workflow,
                        investigator=investigator,
                    ).model_dump(mode="json"),
                    durable_instance_id=instance_id,
                ),
            ),
        ]
    )

    risk_step, failure = _unwrap_activity_response(
        workflow,
        risk_and_persona[0],
        steps,
        context.current_utc_datetime,
    )
    if failure:
        context.set_custom_status(
            {"step": "failed", "message": failure["failure"]["message"]}
        )
        return failure
    persona_step, failure = _unwrap_activity_response(
        workflow,
        risk_and_persona[1],
        steps,
        context.current_utc_datetime,
    )
    if failure:
        context.set_custom_status(
            {"step": "failed", "message": failure["failure"]["message"]}
        )
        return failure

    risk = RiskOutput.model_validate(risk_step["output"])
    persona = PersonaOutput.model_validate(persona_step["output"])

    context.set_custom_status(
        {
            "step": AgentRole.CRITIC.value,
            "message": "Running critic agent...",
            "workflow_id": workflow.workflow_id,
        }
    )
    critic_raw = yield context.call_activity_with_retry(
        "run_agent_step_activity",
        RETRY_OPTIONS,
        _step_request(
            role=AgentRole.CRITIC,
            workflow=workflow,
            stage_input=CriticStageInput(
                workflow=workflow,
                investigator=investigator,
                risk=risk,
                persona=persona,
            ).model_dump(mode="json"),
            durable_instance_id=instance_id,
        ),
    )
    critic_step, failure = _unwrap_activity_response(
        workflow,
        critic_raw,
        steps,
        context.current_utc_datetime,
    )
    if failure:
        context.set_custom_status(
            {"step": "failed", "message": failure["failure"]["message"]}
        )
        return failure
    critic = CriticOutput.model_validate(critic_step["output"])

    context.set_custom_status(
        {
            "step": AgentRole.PLANNER.value,
            "message": "Running remediation planner agent...",
            "workflow_id": workflow.workflow_id,
        }
    )
    planner_raw = yield context.call_activity_with_retry(
        "run_agent_step_activity",
        RETRY_OPTIONS,
        _step_request(
            role=AgentRole.PLANNER,
            workflow=workflow,
            stage_input=PlannerStageInput(
                workflow=workflow,
                investigator=investigator,
                risk=risk,
                persona=persona,
                critic=critic,
            ).model_dump(mode="json"),
            durable_instance_id=instance_id,
        ),
    )
    planner_step, failure = _unwrap_activity_response(
        workflow,
        planner_raw,
        steps,
        context.current_utc_datetime,
    )
    if failure:
        context.set_custom_status(
            {"step": "failed", "message": failure["failure"]["message"]}
        )
        return failure
    planner = PlannerOutput.model_validate(planner_step["output"])

    context.set_custom_status(
        {
            "step": AgentRole.VERIFIER.value,
            "message": "Running verifier agent...",
            "workflow_id": workflow.workflow_id,
        }
    )
    verifier_raw = yield context.call_activity_with_retry(
        "run_agent_step_activity",
        RETRY_OPTIONS,
        _step_request(
            role=AgentRole.VERIFIER,
            workflow=workflow,
            stage_input=VerifierStageInput(
                workflow=workflow,
                investigator=investigator,
                risk=risk,
                persona=persona,
                critic=critic,
                planner=planner,
            ).model_dump(mode="json"),
            durable_instance_id=instance_id,
        ),
    )
    verifier_step, failure = _unwrap_activity_response(
        workflow,
        verifier_raw,
        steps,
        context.current_utc_datetime,
    )
    if failure:
        context.set_custom_status(
            {"step": "failed", "message": failure["failure"]["message"]}
        )
        return failure
    VerifierOutput.model_validate(verifier_step["output"])

    result = AgentWorkflowResult(
        workflow_id=workflow.workflow_id,
        status=WorkflowRunStatus.COMPLETED,
        correlation={
            "correlation_id": workflow.correlation_id,
            "workflow_id": workflow.workflow_id,
            "tenant_id": workflow.tenant_id,
            "project_id": workflow.project_id,
            "trace_id": None,
            "span_id": None,
            "durable_instance_id": instance_id,
        },
        subject_identity_id=workflow.subject.identity_id,
        steps=steps,
        completed_at=context.current_utc_datetime,
    ).model_dump(mode="json")
    context.set_custom_status(
        {
            "step": "completed",
            "message": "Privilege analysis workflow completed.",
            "workflow_id": workflow.workflow_id,
        }
    )
    return result


@bp.orchestration_trigger(context_name="context")
def orchestrate_privilege_analysis(context: df.DurableOrchestrationContext):
    return _orchestrate_privilege_analysis_impl(context)


@bp.activity_trigger(input_name="payload")
def run_agent_step_activity(payload: dict) -> dict:
    """Execute one Microsoft Agent Framework stage and return a typed envelope."""
    set_agent_workflow_context(payload)
    role = payload.get("role", "unknown")
    workflow_id = payload.get("workflow", {}).get("workflow_id", "?")
    try:
        stage = AgentRole(str(role))
    except ValueError:
        stage = AgentRole.INVESTIGATOR
    logger.info(
        "run_agent_step_activity START | workflow=%s | role=%s", workflow_id, role
    )
    try:
        result = run_agent_step_sync(payload)
    except (AgentWorkflowError, ValidationError) as exc:
        logger.exception(
            "run_agent_step_activity FAILED | workflow=%s | role=%s | error=%s",
            workflow_id,
            role,
            exc,
        )
        return AgentStepActivityResponse(
            succeeded=False,
            failure=AgentWorkflowFailure(stage=stage, message=str(exc)),
        ).model_dump(mode="json")
    except Exception as exc:
        logger.exception(
            "run_agent_step_activity FAILED unexpectedly | workflow=%s | role=%s | error=%s",
            workflow_id,
            role,
            exc,
        )
        return AgentStepActivityResponse(
            succeeded=False,
            failure=AgentWorkflowFailure(
                stage=stage,
                message="Agent activity failed unexpectedly",
            ),
        ).model_dump(mode="json")

    logger.info(
        "run_agent_step_activity DONE | workflow=%s | role=%s", workflow_id, role
    )
    return AgentStepActivityResponse(
        succeeded=True,
        result=result,
    ).model_dump(mode="json")
