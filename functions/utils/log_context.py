"""Structured logging context for App Insights custom dimensions.

Sets scan_id, project_id, and tenant_id on every log record via
contextvars so the Azure Functions App Insights exporter picks them
up as customDimensions — queryable as:
    customDimensions.scan_id == "abc-123"
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

_scan_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "scan_id", default=None
)
_project_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "project_id", default=None
)
_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)
_workflow_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "workflow_id", default=None
)
_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
_agent_role: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "agent_role", default=None
)
_prompt_version: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "prompt_version", default=None
)


class ScanContextFilter(logging.Filter):
    """Injects scan context into log records as custom_dimensions."""

    def filter(self, record: logging.LogRecord) -> bool:
        dims: dict[str, Any] = getattr(record, "custom_dimensions", None) or {}

        scan_id = _scan_id.get()
        project_id = _project_id.get()
        tenant_id = _tenant_id.get()
        workflow_id = _workflow_id.get()
        correlation_id = _correlation_id.get()
        agent_role = _agent_role.get()
        prompt_version = _prompt_version.get()

        if scan_id:
            dims["scan_id"] = scan_id
        if project_id:
            dims["project_id"] = project_id
        if tenant_id:
            dims["tenant_id"] = tenant_id
        if workflow_id:
            dims["workflow_id"] = workflow_id
        if correlation_id:
            dims["correlation_id"] = correlation_id
        if agent_role:
            dims["agent_role"] = agent_role
        if prompt_version:
            dims["prompt_version"] = prompt_version

        record.custom_dimensions = dims  # type: ignore[attr-defined]
        return True


def set_scan_context(payload: dict[str, Any]) -> None:
    """Set scan context vars from an activity payload dict."""
    _scan_id.set(payload.get("scan_id"))
    _project_id.set(payload.get("project_id"))
    _tenant_id.set(payload.get("tenant_id"))


def set_agent_workflow_context(payload: dict[str, Any]) -> None:
    """Set agent workflow correlation context vars from an activity payload dict."""
    workflow = (
        payload.get("workflow")
        if isinstance(payload.get("workflow"), dict)
        else payload
    )
    _scan_id.set(None)
    _project_id.set(workflow.get("project_id"))
    _tenant_id.set(workflow.get("tenant_id"))
    _workflow_id.set(workflow.get("workflow_id"))
    _correlation_id.set(workflow.get("correlation_id"))
    _agent_role.set(payload.get("role"))
    _prompt_version.set(workflow.get("prompt_bundle_version"))
