# backend/app/models/identity.py
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class IdentityType(StrEnum):
    """Types of Entra ID identity principals."""

    USER = "User"
    SERVICE_PRINCIPAL = "ServicePrincipal"
    MANAGED_IDENTITY = "ManagedIdentity"
    GROUP = "Group"


class ObservedAction(BaseModel):
    """An aggregated action observed for an identity."""

    action: str
    resource: str | None = None
    count: int = 0
    first_seen: datetime
    last_seen: datetime


class CurrentRole(BaseModel):
    """A role currently assigned to an identity."""

    role_id: str
    role_name: str
    scope: str = "/"
    assignment_type: str = "direct"  # "direct" | "group" | "pim_eligible" | "pim_activated"
    is_permanent: bool = True
    start_date: datetime | None = None
    end_date: datetime | None = None
    member_type: str = "Direct"  # "Direct" | "Inherited" | "Group"
    eligibility_schedule_id: str | None = None
    activated_using_id: str | None = None


class RiskDetectionSummary(BaseModel):
    """Summarized risk detection from Entra ID Protection."""

    id: str
    risk_event_type: str
    risk_level: str = "none"
    risk_state: str = "none"
    detection_timing: str = "offline"
    activity_date_time: datetime
    detected_date_time: datetime
    ip_address: str | None = None
    location: str | None = None
    source: str | None = None


class GroupMembershipInfo(BaseModel):
    """Group membership record for an identity."""

    group_id: str
    group_display_name: str
    is_role_assignable: bool = False
    is_dynamic: bool = False
    membership_rule: str | None = None
    is_direct: bool = True
    roles_inherited: list[str] = []


class IdentityProfile(BaseModel):
    """Full identity profile stored in Cosmos DB.

    The ``id`` field follows the pattern ``{identityType}_{objectId}`` to ensure
    uniqueness across identity types within a tenant.
    """

    model_config = ConfigDict(extra="ignore")

    id: str  # {identityType}_{objectId}
    tenant_id: str
    identity_type: IdentityType
    object_id: str
    display_name: str
    upn: str | None = None
    app_id: str | None = None
    current_roles: list[CurrentRole] = []
    eligible_roles: list[CurrentRole] = []
    observed_actions: list[ObservedAction] = []
    risk_score: float = 0.0
    action_count: int = 0
    last_seen: datetime | None = None
    first_seen: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Guest / B2B fields
    user_type: str | None = None
    external_user_state: str | None = None
    external_user_state_change: datetime | None = None

    # Sign-in activity (from Graph signInActivity property)
    last_sign_in_at: datetime | None = None
    last_non_interactive_sign_in_at: datetime | None = None

    creation_type: str | None = None
    identity_providers: list[str] = []

    # Identity Protection fields
    entra_risk_level: str | None = None
    entra_risk_state: str | None = None
    entra_risk_detail: str | None = None
    entra_risk_updated_at: datetime | None = None
    active_risk_detections: list[RiskDetectionSummary] = []

    # Group membership
    group_memberships: list[GroupMembershipInfo] = []
    effective_roles_via_groups: list[CurrentRole] = []

    # Access review coverage
    covered_by_access_review: bool = False
    access_review_ids: list[str] = []

    # Account status
    account_enabled: bool | None = None

    # Location profile (for geo-anomaly detection)
    known_locations: list[dict[str, str]] = []
