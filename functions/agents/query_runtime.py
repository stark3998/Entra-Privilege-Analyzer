"""Scoped Copilot query endpoint runtime."""

from __future__ import annotations

import logging
from typing import Any

from agent_framework import Agent, FunctionTool
from agent_framework_foundry import FoundryChatClient
from pydantic import Field

from agents.errors import AgentExecutionError, AgentWorkflowConfigurationError
from agents.models import (
    AgentDescriptor,
    AgentQueryOutput,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentRole,
    CorrelationContext,
    QueryTrace,
    StrictModel,
)
from agents.prompts import PromptTemplate
from agents.routing import ModelRouter
from agents.runtime import _get_credential
from agents.telemetry import start_agent_span
from utils.project_evidence import ProjectEvidenceAccessor

logger = logging.getLogger(__name__)

_QUERY_PROMPT = PromptTemplate(
    role=None,
    name="entra.scoped_copilot_query",
    description="Answer read-only governance questions from scoped project evidence.",
    instructions=(
        "You are the Entra Privilege Analyzer scoped copilot query agent.\n"
        "Use only the provided read-only tools and the caller's question.\n"
        "Never fabricate identities, roles, permissions, or evidence.\n"
        "Every finding must cite one or more evidence identifiers returned by tools.\n"
        "If the evidence is insufficient, state that explicitly in limitations.\n"
        "Return only the requested structured schema."
    ),
    version="2026-09-15.2",
)


class EvidenceIdInput(StrictModel):
    evidence_id: str = Field(min_length=1)


class SearchEvidenceInput(StrictModel):
    query: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=8, ge=1, le=25)


class IdentityProfileInput(StrictModel):
    identity_id: str | None = None


class ScopeEvidenceInput(StrictModel):
    limit: int = Field(default=8, ge=1, le=25)


class QueryAgentRunner:
    """Run the scoped copilot agent against project evidence."""

    def __init__(self, model_router: ModelRouter | None = None) -> None:
        self._model_router = model_router or ModelRouter()

    async def run(self, request: AgentQueryRequest) -> AgentQueryResponse:
        accessor = ProjectEvidenceAccessor(request)
        route = self._resolve_route()
        client = self._build_client(route.model)
        tools = self._build_tools(accessor)
        prompt = _QUERY_PROMPT
        trace = QueryTrace(correlation_id=request.correlation_id)

        agent = Agent(
            client=client,
            instructions=prompt.instructions,
            name="scoped-copilot-query",
            description="Read-only scoped copilot query agent for Entra governance evidence.",
            tools=tools,
        )

        logger.info(
            "agent_query START | project=%s | tenant=%s | correlation=%s | model=%s",
            request.project_id,
            request.tenant_id,
            request.correlation_id,
            route.model,
        )
        with start_agent_span(
            role=self._query_role,
            correlation=CorrelationContext(
                correlation_id=request.correlation_id,
                workflow_id=f"agent-query:{request.project_id}",
                tenant_id=request.tenant_id,
                project_id=request.project_id,
                durable_instance_id=None,
            ),
            prompt=prompt,
            route=route,
            tool_names=[tool.name for tool in tools],
        ) as span:
            response = await agent.run(
                self._build_user_message(request),
                options={
                    "response_format": AgentQueryOutput,
                    "temperature": route.temperature,
                    "max_tokens": route.max_tokens,
                    "verbosity": route.verbosity,
                    "metadata": {
                        "project_id": request.project_id,
                        "tenant_id": request.tenant_id,
                        "correlation_id": request.correlation_id,
                        "prompt_name": prompt.name,
                        "prompt_version": prompt.version,
                    },
                    "user": request.user_id,
                    "tool_choice": "auto",
                    "allow_multiple_tool_calls": True,
                    "max_tool_calls": 12,
                },
            )
            span_context = span.get_span_context()
            if span_context.trace_id:
                trace.trace_id = format(span_context.trace_id, "032x")
            if span_context.span_id:
                trace.span_id = format(span_context.span_id, "016x")

        output = self._parse_output(response)
        evidence_ids = sorted(
            {
                evidence_id
                for citation in output.citations
                for evidence_id in [citation.evidence_id]
            }
            | {
                evidence_id
                for finding in output.structured_answer.findings
                for evidence_id in finding.evidence_ids
            }
        )
        if not evidence_ids:
            raise AgentExecutionError(
                "Scoped copilot response contained no evidence identifiers"
            )
        accessor.validate_evidence_ids(evidence_ids)

        answer_text = self._render_answer_text(output)
        logger.info(
            "agent_query DONE | project=%s | tenant=%s | correlation=%s | evidence_ids=%d",
            request.project_id,
            request.tenant_id,
            request.correlation_id,
            len(evidence_ids),
        )
        return AgentQueryResponse(
            answer=answer_text,
            structured_answer=output.structured_answer,
            citations=output.citations,
            evidence_ids=evidence_ids,
            agent=AgentDescriptor(
                name="scoped-copilot-query",
                role="investigator",
                version=prompt.version,
                prompt_name=prompt.name,
                prompt_version=prompt.version,
                model=route.model,
                provider=route.provider,
            ),
            version=prompt.version,
            correlation_id=request.correlation_id,
            trace=trace,
        )

    @property
    def _query_role(self):
        return AgentRole.INVESTIGATOR

    def _resolve_route(self):
        return self._model_router.resolve_query()

    @staticmethod
    def _build_user_message(request: AgentQueryRequest) -> str:
        return (
            f"Question: {request.query}\n"
            f"Project: {request.project_id}\n"
            f"Tenant: {request.tenant_id}\n"
            f"Scope: {request.scope}\n"
            "Answer the question with grounded findings and citations."
        )

    @staticmethod
    def _build_client(model: str) -> FoundryChatClient:
        import os

        project_endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
        if not project_endpoint:
            raise AgentWorkflowConfigurationError(
                "FOUNDRY_PROJECT_ENDPOINT must be configured for agent queries."
            )
        return FoundryChatClient(
            project_endpoint=project_endpoint,
            model=model,
            credential=_get_credential(),
        )

    @staticmethod
    def _build_tools(accessor: ProjectEvidenceAccessor) -> list[FunctionTool]:
        return [
            FunctionTool(
                name="get_project_summary",
                description="Return read-only project metadata and query scope context.",
                func=accessor.get_project_summary,
                approval_mode="never_require",
            ),
            FunctionTool(
                name="list_scope_evidence",
                description="List evidence already scoped by the request, such as a focused identity and related findings.",
                func=accessor.list_scope_evidence,
                input_model=ScopeEvidenceInput,
                approval_mode="never_require",
            ),
            FunctionTool(
                name="search_evidence",
                description="Search read-only project evidence for identities, risks, recommendations, or violations relevant to the question.",
                func=accessor.search_evidence,
                input_model=SearchEvidenceInput,
                approval_mode="never_require",
            ),
            FunctionTool(
                name="get_identity_profile",
                description="Return a detailed identity profile for a specific identity identifier.",
                func=accessor.get_identity_profile,
                input_model=IdentityProfileInput,
                approval_mode="never_require",
            ),
            FunctionTool(
                name="get_evidence_detail",
                description="Resolve a specific evidence identifier into its underlying record.",
                func=accessor.get_evidence_detail,
                input_model=EvidenceIdInput,
                approval_mode="never_require",
            ),
        ]

    @staticmethod
    def _parse_output(response: Any) -> AgentQueryOutput:
        value = getattr(response, "value", None)
        if isinstance(value, AgentQueryOutput):
            return value
        if isinstance(value, dict):
            return AgentQueryOutput.model_validate(value)
        text = getattr(response, "text", None)
        if text:
            return AgentQueryOutput.model_validate_json(text)
        raise AgentExecutionError(
            "Scoped copilot response did not contain structured output"
        )

    @staticmethod
    def _render_answer_text(output: AgentQueryOutput) -> str:
        lines = [output.structured_answer.summary]
        for finding in output.structured_answer.findings[:3]:
            lines.append(f"- {finding.title}: {finding.summary}")
        if output.structured_answer.next_steps:
            lines.append(
                "Next steps: " + "; ".join(output.structured_answer.next_steps[:3])
            )
        return "\n".join(lines)
