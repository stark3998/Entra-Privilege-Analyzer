from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ScanPhase(BaseModel):
    """Progress tracking for a single phase within a scan."""

    name: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items_processed: int = 0


class ScanRecord(BaseModel):
    """Record of a scan execution for a project."""

    model_config = ConfigDict(extra="ignore")

    id: str
    project_id: str
    target_tenant_id: str
    scan_type: Literal["full", "incremental"] = "full"
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    auth_mode: Literal["app", "delegated"] = "app"
    phases: list[ScanPhase] = []
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class ProjectMember(BaseModel):
    """Membership record linking a user to a project with a role."""

    model_config = ConfigDict(extra="ignore")

    id: str
    project_id: str
    user_id: str
    email: str
    role: Literal["admin", "operator", "viewer"] = "viewer"
    invited_by: str
    status: Literal["pending", "accepted"] = "accepted"
    created_at: datetime


class Project(BaseModel):
    """A project targeting a specific Entra ID tenant for analysis."""

    model_config = ConfigDict(extra="ignore")

    id: str
    owner_id: str
    owner_email: str = ""
    name: str
    target_tenant_id: str
    target_tenant_name: str
    client_id: str = ""
    encrypted_client_secret: str = ""
    status: Literal["active", "setup", "error"] = "setup"
    permission_status: dict[str, Any] | None = None
    last_scan_at: datetime | None = None
    last_scan_status: str | None = None
    identity_count: int = 0
    risk_score: float = 0.0
    sync_schedule_hours: int = 6
    baseline_window_days: int = 30
    created_at: datetime
    updated_at: datetime
