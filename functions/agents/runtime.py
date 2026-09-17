"""Microsoft Agent Framework runtime for durable Functions workflows."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, ValidationError

from agents.errors import AgentExecutionError, AgentWorkflowConfigurationError
from agents.models import (
    AgentRole,
    AgentStageResult,
    CriticOutput,
    CriticStageInput,
    InvestigatorOutput,
    InvestigatorStageInput,
    PersonaOutput,
    PersonaStageInput,
    PlannerOutput,
    PlannerStageInput,
    RiskOutput,
    RiskStageInput,
    RunAgentStepRequest,
    ToolPolicy,
    VerifierOutput,
    VerifierStageInput,
)
from agents.prompts import PromptTemplate, get_prompt
from agents.routing import ModelRouter
from agents.telemetry import (
    build_correlation_context,
    build_request_metadata,
    start_agent_span,
)
from agents.tools import WorkflowEvidenceTools

logger = logging.getLogger(__name__)


class ScopedCopilotAgent:
    """Typed Agent Framework abstraction with a strict read-only tool scope."""

    role: AgentRole
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    allowed_tools: tuple[str, ...]

    def prompt(self) -> PromptTemplate:
        return get_prompt(self.role)

    def validate_input(self, payload: dict[str, Any]) -> BaseModel:
        return self.input_model.model_validate(payload)

    def build_user_message(self, payload: BaseModel) -> str:
        serialized = json.dumps(
            payload.model_dump(mode="json"), indent=2, sort_keys=True
        )
        return (
            f"Workflow stage: {self.role.value}\n"
            "Return a single response that matches the structured schema exactly.\n"
            "Ground every conclusion in the stage input and tool results.\n\n"
            f"Stage input JSON:\n{serialized}"
        )


class ReadOnlyInvestigatorAgent(ScopedCopilotAgent):
    role = AgentRole.INVESTIGATOR
    name = "read-only-investigator"
    description = (
        "Collects grounded least-privilege evidence from immutable workflow data."
    )
    input_model = InvestigatorStageInput
    output_model = InvestigatorOutput
    allowed_tools = (
        "get_subject_summary",
        "list_roles",
        "list_observed_actions",
        "list_risk_signals",
        "list_persona_candidates",
        "list_governance_constraints",
        "search_permission_catalog",
        "search_builtin_roles",
    )


class RiskAgent(ScopedCopilotAgent):
    role = AgentRole.RISK
    name = "risk-agent"
    description = "Scores exposure, impact, and confidence from grounded evidence."
    input_model = RiskStageInput
    output_model = RiskOutput
    allowed_tools = (
        "get_subject_summary",
        "list_roles",
        "list_observed_actions",
        "list_risk_signals",
        "search_permission_catalog",
        "search_builtin_roles",
    )


class PersonaAgent(ScopedCopilotAgent):
    role = AgentRole.PERSONA
    name = "persona-agent"
    description = "Compares the subject to peer personas and least-privilege baselines."
    input_model = PersonaStageInput
    output_model = PersonaOutput
    allowed_tools = (
        "get_subject_summary",
        "list_roles",
        "list_observed_actions",
        "list_persona_candidates",
        "search_permission_catalog",
        "search_builtin_roles",
    )


class CriticAgent(ScopedCopilotAgent):
    role = AgentRole.CRITIC
    name = "critic-agent"
    description = "Challenges unsupported claims and forces explicit uncertainty."
    input_model = CriticStageInput
    output_model = CriticOutput
    allowed_tools = (
        "get_subject_summary",
        "list_roles",
        "list_observed_actions",
        "list_risk_signals",
        "list_persona_candidates",
        "list_governance_constraints",
    )


class PlannerAgent(ScopedCopilotAgent):
    role = AgentRole.PLANNER
    name = "planner-agent"
    description = "Creates reversible least-privilege remediation plans."
    input_model = PlannerStageInput
    output_model = PlannerOutput
    allowed_tools = (
        "get_subject_summary",
        "list_roles",
        "list_risk_signals",
        "list_governance_constraints",
        "search_permission_catalog",
        "search_builtin_roles",
    )


class VerifierAgent(ScopedCopilotAgent):
    role = AgentRole.VERIFIER
    name = "verifier-agent"
    description = "Verifies that the remediation plan is grounded and release-safe."
    input_model = VerifierStageInput
    output_model = VerifierOutput
    allowed_tools = (
        "get_subject_summary",
        "list_roles",
        "list_observed_actions",
        "list_governance_constraints",
    )


_AGENTS: dict[AgentRole, ScopedCopilotAgent] = {
    AgentRole.INVESTIGATOR: ReadOnlyInvestigatorAgent(),
    AgentRole.RISK: RiskAgent(),
    AgentRole.PERSONA: PersonaAgent(),
    AgentRole.CRITIC: CriticAgent(),
    AgentRole.PLANNER: PlannerAgent(),
    AgentRole.VERIFIER: VerifierAgent(),
}
_RUNNER: AgentWorkflowRunner | None = None
_CACHED_CREDENTIAL: DefaultAzureCredential | None = None


def _get_credential() -> DefaultAzureCredential:
    global _CACHED_CREDENTIAL
    if _CACHED_CREDENTIAL is None:
        _CACHED_CREDENTIAL = DefaultAzureCredential(
            exclude_interactive_browser_credential=True
        )
    return _CACHED_CREDENTIAL


class AgentWorkflowRunner:
    """Resolve role-specific agents, tools, prompts, and models for one workflow step."""

    def __init__(
        self,
        *,
        model_router: ModelRouter | None = None,
        client_factory: Any | None = None,
    ) -> None:
        self._model_router = model_router or ModelRouter()
        self._client_factory = client_factory or self._build_foundry_client

    async def run_step(self, request: RunAgentStepRequest) -> AgentStageResult:
        scoped_agent = _AGENTS[request.role]
        workflow = request.workflow
        stage_input = scoped_agent.validate_input(request.stage_input)
        prompt = scoped_agent.prompt()
        override = workflow.model_overrides.get(request.role)
        route = self._model_router.resolve(request.role, override_model=override)
        correlation = build_correlation_context(
            workflow_id=workflow.workflow_id,
            correlation_id=workflow.correlation_id,
            tenant_id=workflow.tenant_id,
            project_id=workflow.project_id,
            durable_instance_id=request.durable_instance_id,
        )
        evidence_tools = WorkflowEvidenceTools(workflow)
        tool_names = list(scoped_agent.allowed_tools)
        tools = evidence_tools.materialize(scoped_agent.allowed_tools)
        client = self._client_factory(route)
        agent = Agent(
            client=client,
            instructions=prompt.instructions,
            name=scoped_agent.name,
            description=scoped_agent.description,
            tools=tools,
        )

        logger.info(
            "agent_step START | workflow=%s | role=%s | model=%s | tools=%s",
            workflow.workflow_id,
            request.role.value,
            route.model,
            ",".join(tool_names),
        )
        started_at = datetime.now(UTC)
        metadata = build_request_metadata(correlation, request.role, prompt, route)

        with start_agent_span(
            role=request.role,
            correlation=correlation,
            prompt=prompt,
            route=route,
            tool_names=tool_names,
        ):
            response = await agent.run(
                scoped_agent.build_user_message(stage_input),
                options={
                    "response_format": scoped_agent.output_model,
                    "temperature": route.temperature,
                    "max_tokens": route.max_tokens,
                    "verbosity": route.verbosity,
                    "metadata": metadata,
                    "user": workflow.requested_by,
                    "tool_choice": "auto" if tools else "none",
                    "allow_multiple_tool_calls": True,
                    "max_tool_calls": max(1, len(tools) * 2),
                },
            )

        parsed_output = self._parse_output(response, scoped_agent.output_model)
        completed_at = datetime.now(UTC)
        usage = self._serialize_usage(getattr(response, "usage_details", None))

        logger.info(
            "agent_step DONE | workflow=%s | role=%s | model=%s | response_id=%s",
            workflow.workflow_id,
            request.role.value,
            route.model,
            getattr(response, "response_id", None),
        )

        return AgentStageResult(
            role=request.role,
            prompt=prompt.metadata(),
            model_route=route,
            tool_policy=ToolPolicy(allowlist=tool_names),
            correlation=correlation,
            output_model=scoped_agent.output_model.__name__,
            started_at=started_at,
            completed_at=completed_at,
            response_id=getattr(response, "response_id", None),
            finish_reason=str(getattr(response, "finish_reason", "")) or None,
            usage=usage,
            output=parsed_output.model_dump(mode="json"),
        )

    def _build_foundry_client(self, route) -> FoundryChatClient:
        project_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        if not project_endpoint:
            raise AgentWorkflowConfigurationError(
                "FOUNDRY_PROJECT_ENDPOINT must be configured for Functions agent workflows."
            )
        return FoundryChatClient(
            project_endpoint=project_endpoint,
            model=route.model,
            credential=_get_credential(),
        )

    @staticmethod
    def _parse_output(response: Any, output_model: type[BaseModel]) -> BaseModel:
        value = getattr(response, "value", None)
        if isinstance(value, output_model):
            return value
        if isinstance(value, BaseModel):
            return output_model.model_validate(value.model_dump(mode="json"))
        if isinstance(value, dict):
            return output_model.model_validate(value)

        text = getattr(response, "text", None)
        if text:
            try:
                return output_model.model_validate_json(text)
            except ValidationError as exc:
                raise AgentExecutionError(
                    f"Structured output for {output_model.__name__} was invalid JSON: {exc}"
                ) from exc

        raise AgentExecutionError(
            f"Agent response did not contain a structured {output_model.__name__} payload"
        )

    @staticmethod
    def _serialize_usage(usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if hasattr(usage, "to_dict"):
            return usage.to_dict()
        if isinstance(usage, BaseModel):
            return usage.model_dump(mode="json")
        if isinstance(usage, dict):
            return usage
        return {"value": str(usage)}


def run_agent_step_sync(payload: dict[str, Any]) -> AgentStageResult:
    request = RunAgentStepRequest.model_validate(payload)
    return asyncio.run(get_agent_workflow_runner().run_step(request))


def get_agent_workflow_runner() -> AgentWorkflowRunner:
    global _RUNNER
    if _RUNNER is None:
        _RUNNER = AgentWorkflowRunner()
    return _RUNNER
