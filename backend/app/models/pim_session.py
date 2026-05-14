from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class PimSessionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DEACTIVATED = "deactivated"


class PimSessionScope(StrEnum):
    ENTRA_DIRECTORY = "entra_directory"
    AZURE_RBAC = "azure_rbac"


class PimSessionAnomalyType(StrEnum):
    UNUSUAL_ACTIVATION_TIME = "unusual_activation_time"
    NEW_LOCATION = "new_location"
    FIRST_TIME_ROLE = "first_time_role"
    HIGH_VOLUME_ACTIONS = "high_volume_actions"
    SENSITIVE_ACTION = "sensitive_action"
    NO_JUSTIFICATION = "no_justification"


class TicketInfo(BaseModel):
    ticket_number: str | None = None
    ticket_system: str | None = None


class ApprovalInfo(BaseModel):
    approval_id: str | None = None
    approver_id: str | None = None
    approver_display_name: str | None = None
    approval_status: str | None = None
    approved_at: datetime | None = None


class SessionLocationInfo(BaseModel):
    ip_address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class PimSessionAnomaly(BaseModel):
    anomaly_type: PimSessionAnomalyType
    severity: str = "medium"
    details: str
    detected_at: datetime


class PimSession(BaseModel):
    """A privileged session representing a PIM role activation window."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    principal_id: str
    principal_display_name: str
    principal_upn: str | None = None
    identity_id: str

    role_definition_id: str
    role_name: str
    scope: str = "/"
    session_scope: PimSessionScope = PimSessionScope.ENTRA_DIRECTORY

    activation_time: datetime
    expiry_time: datetime
    actual_deactivation_time: datetime | None = None
    duration_minutes: int = 0

    status: PimSessionStatus = PimSessionStatus.ACTIVE
    is_active: bool = False

    justification: str | None = None
    ticket_info: TicketInfo | None = None
    approval_info: ApprovalInfo | None = None
    activation_request_id: str | None = None

    audit_event_count: int = 0
    sign_in_event_count: int = 0
    total_event_count: int = 0
    unique_actions: list[str] = []
    locations: list[SessionLocationInfo] = []

    anomalies: list[PimSessionAnomaly] = []
    risk_score: float = 0.0

    created_at: datetime
    updated_at: datetime
    last_event_sync_at: datetime | None = None

    raw_request_data: dict[str, Any] | None = None


class PimSessionAnalytics(BaseModel):
    """Cross-session analytics for the PIM governance dashboard."""

    tenant_id: str
    total_sessions: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    sessions_with_anomalies: int = 0
    avg_session_duration_minutes: float = 0.0
    top_activated_roles: list[dict[str, Any]] = []
    top_activators: list[dict[str, Any]] = []
    activations_by_hour: dict[int, int] = {}
    activations_by_day: list[dict[str, Any]] = []
    anomaly_counts_by_type: dict[str, int] = {}
    computed_at: datetime
