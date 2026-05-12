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
    scope: str  # "/" for directory, or resource scope
    assignment_type: str = "direct"  # "direct" | "group" | "pim"
    is_permanent: bool = True


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
    upn: str | None = None  # for users
    app_id: str | None = None  # for service principals
    current_roles: list[CurrentRole] = []
    observed_actions: list[ObservedAction] = []
    risk_score: float = 0.0
    action_count: int = 0
    last_seen: datetime | None = None
    first_seen: datetime | None = None
    created_at: datetime
    updated_at: datetime
