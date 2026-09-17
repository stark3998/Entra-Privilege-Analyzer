"""OpenTelemetry helpers for Functions-hosted agent workflows."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from opentelemetry import trace

from agents.models import AgentRole, CorrelationContext, ModelRoute
from agents.prompts import PromptTemplate

_TRACER = trace.get_tracer("functions.agents")


def build_correlation_context(
    *,
    workflow_id: str,
    correlation_id: str,
    tenant_id: str,
    project_id: str,
    durable_instance_id: str | None = None,
) -> CorrelationContext:
    span = trace.get_current_span()
    span_context = span.get_span_context()
    trace_id = format(span_context.trace_id, "032x") if span_context.trace_id else None
    span_id = format(span_context.span_id, "016x") if span_context.span_id else None
    return CorrelationContext(
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        project_id=project_id,
        trace_id=trace_id,
        span_id=span_id,
        durable_instance_id=durable_instance_id,
    )


def build_request_metadata(
    correlation: CorrelationContext,
    role: AgentRole,
    prompt: PromptTemplate,
    route: ModelRoute,
) -> dict[str, Any]:
    return {
        "correlation_id": correlation.correlation_id,
        "workflow_id": correlation.workflow_id,
        "project_id": correlation.project_id,
        "tenant_id": correlation.tenant_id,
        "agent_role": role.value,
        "prompt_name": prompt.name,
        "prompt_version": prompt.version,
        "model": route.model,
        "provider": route.provider,
        "durable_instance_id": correlation.durable_instance_id,
    }


@contextmanager
def start_agent_span(
    *,
    role: AgentRole,
    correlation: CorrelationContext,
    prompt: PromptTemplate,
    route: ModelRoute,
    tool_names: list[str],
):
    with _TRACER.start_as_current_span(
        f"agent_workflow.{role.value}",
        attributes={
            "agent.role": role.value,
            "agent.model": route.model,
            "agent.provider": route.provider,
            "prompt.name": prompt.name,
            "prompt.version": prompt.version,
            "workflow.id": correlation.workflow_id,
            "workflow.correlation_id": correlation.correlation_id,
            "project.id": correlation.project_id,
            "tenant.id": correlation.tenant_id,
            "durable.instance_id": correlation.durable_instance_id or "",
            "tool.allowlist": ",".join(tool_names),
        },
    ) as span:
        yield span
