from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ScanPhase(BaseModel):
    """Progress tracking for a single phase within a scan."""

    name: str
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    items_processed: int = 0
    checkpoint_next_link: str | None = None


class ScanLogEntry(BaseModel):
    """A single persisted log event from a scan run."""

    model_config = ConfigDict(extra="ignore")

    id: str
    scan_id: str
    project_id: str
    type: str
    message: str
    level: str = "info"
    phase: str | None = None
    status: str | None = None
    items_processed: int | None = None
    timestamp: datetime
    details: dict[str, Any] = {}
    ttl: int = 7776000


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
    owner_instance_id: str | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    completed_at: datetime | None = None
    resumed_from_scan_id: str | None = None
    error_message: str | None = None
    orchestration_instance_id: str | None = None
    orchestration_status_uri: str | None = None


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
    azure_subscription_ids: list[str] = []
    created_at: datetime
    updated_at: datetime
