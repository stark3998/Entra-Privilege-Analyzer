# backend/app/models/best_practice.py
"""Pydantic v2 models for best practice violation analysis."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ViolationType(StrEnum):
    """Categories of best practice violations."""

    STALE_IDENTITY = "stale_identity"
    PERMANENT_ADMIN = "permanent_admin"
    NO_PIM = "no_pim"
    SP_CREDENTIAL_EXPIRY = "sp_credential_expiry"
    SEPARATION_OF_DUTIES = "separation_of_duties"
    OVERPRIVILEGED = "overprivileged"
    MFA_GAP = "mfa_gap"
    ROLE_ASSIGNABLE_GROUP = "role_assignable_group"


class ViolationPriority(StrEnum):
    """Priority level for a violation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BestPracticeViolation(BaseModel):
    """A single best practice violation for an identity."""

    model_config = ConfigDict(extra="ignore")

    id: str  # {identity_id}_{violation_type}
    tenant_id: str
    identity_id: str
    identity_display_name: str
    identity_type: str
    violation_type: ViolationType
    priority: ViolationPriority
    title: str
    description: str
    remediation_steps: list[str]
    affected_roles: list[str]
    detected_at: datetime
    resolved: bool = False


class BestPracticeSummary(BaseModel):
    """Aggregated compliance summary for a tenant."""

    tenant_id: str
    total_violations: int
    by_priority: dict[str, int]
    by_type: dict[str, int]
    compliance_score: float  # 0-100
    evaluated_at: datetime
