# backend/app/models/action.py
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ActionSource(StrEnum):
    """Origin of an observed action event."""

    AUDIT_LOG = "audit_log"
    SIGN_IN_LOG = "sign_in_log"
    ACTIVITY_LOG = "activity_log"


class ActionEvent(BaseModel):
    """A single action event recorded from Microsoft Graph logs.

    The ``id`` is a deterministic UUID derived from source fields to prevent
    duplicate ingestion on re-runs.
    """

    id: str  # UUID (deterministic)
    tenant_id: str
    identity_id: str  # references IdentityProfile.id
    identity_display_name: str
    action: str  # e.g. "Add user", "Update application"
    resource: str | None = None  # target resource
    resource_type: str | None = None
    result: str = "success"  # "success" | "failure"
    source: ActionSource
    correlation_id: str | None = None
    ip_address: str | None = None
    timestamp: datetime
    raw_data: dict[str, Any] | None = None  # original log entry (optional)
