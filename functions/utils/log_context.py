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

_scan_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("scan_id", default=None)
_project_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("project_id", default=None)
_tenant_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_id", default=None)


class ScanContextFilter(logging.Filter):
    """Injects scan context into log records as custom_dimensions."""

    def filter(self, record: logging.LogRecord) -> bool:
        dims: dict[str, Any] = getattr(record, "custom_dimensions", None) or {}

        scan_id = _scan_id.get()
        project_id = _project_id.get()
        tenant_id = _tenant_id.get()

        if scan_id:
            dims["scan_id"] = scan_id
        if project_id:
            dims["project_id"] = project_id
        if tenant_id:
            dims["tenant_id"] = tenant_id

        record.custom_dimensions = dims  # type: ignore[attr-defined]
        return True


def set_scan_context(payload: dict[str, Any]) -> None:
    """Set scan context vars from an activity payload dict."""
    _scan_id.set(payload.get("scan_id"))
    _project_id.set(payload.get("project_id"))
    _tenant_id.set(payload.get("tenant_id"))
