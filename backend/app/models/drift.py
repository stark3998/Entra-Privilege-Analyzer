# backend/app/models/drift.py
"""Pydantic v2 models for permission drift detection."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DriftSeverity(StrEnum):
    """Severity level of a drift alert."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftStatus(StrEnum):
    """Workflow status of a drift alert."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class DriftType(StrEnum):
    """Detection method that produced the alert."""

    FIRST_SEEN = "first_seen"
    FREQUENCY_ANOMALY = "frequency_anomaly"
    IDENTITY_PROTECTION = "identity_protection"
    GUEST_PRIVILEGE_ESCALATION = "guest_privilege_escalation"
    GROUP_ROLE_CHANGE = "group_role_change"


class DriftAlert(BaseModel):
    """A single drift alert for an identity."""

    model_config = ConfigDict(extra="ignore")

    id: str  # UUID
    tenant_id: str
    identity_id: str
    identity_display_name: str
    drift_type: DriftType
    action: str
    resource: str | None = None
    severity: DriftSeverity
    status: DriftStatus = DriftStatus.OPEN
    z_score: float | None = None  # only for frequency_anomaly
    baseline_mean: float | None = None
    baseline_stddev: float | None = None
    observed_count: int | None = None
    details: str
    detected_at: datetime
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    risk_event_type: str | None = None
    risk_detection_id: str | None = None
    entra_risk_level: str | None = None


class BaselineStats(BaseModel):
    """Rolling baseline statistics for an identity's action."""

    model_config = ConfigDict(extra="ignore")

    id: str  # {identity_id}_{action_hash}
    identity_id: str
    tenant_id: str
    action: str
    resource: str | None = None
    mean: float
    stddev: float
    sample_count: int
    window_start: datetime
    window_end: datetime
    updated_at: datetime


class DriftAlertUpdate(BaseModel):
    """Payload for updating a drift alert status."""

    status: DriftStatus
    acknowledged_by: str | None = None
