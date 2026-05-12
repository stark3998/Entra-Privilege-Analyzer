# backend/app/models/role.py
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.models.identity import CurrentRole


class RoleScope(StrEnum):
    """Scope of a role — Entra ID directory or Azure RBAC."""

    ENTRA = "entra"
    AZURE = "azure"


class PermissionGap(BaseModel):
    """A permission that the identity holds but has not used (overprivilege indicator)."""

    permission: str
    risk_weight: str  # "low" | "medium" | "high" | "critical"
    is_used: bool


class BuiltInRoleMatch(BaseModel):
    """Describes how well a built-in role matches required permissions."""

    role_id: str
    role_name: str
    scope: RoleScope
    match_score: float  # 0.0–1.0
    permissions_matched: int
    permissions_total: int
    excess_permissions: list[str]


class CustomRoleDefinition(BaseModel):
    """A custom role scoped to exactly the required permissions."""

    name: str
    description: str
    scope: RoleScope
    permissions: list[str]
    is_assignable_scopes: list[str]


class RoleRecommendation(BaseModel):
    """Full recommendation for a single identity."""

    model_config = ConfigDict(extra="ignore")

    id: str  # = identity_id
    tenant_id: str
    identity_id: str
    identity_display_name: str
    identity_type: str
    current_roles: list[CurrentRole]
    required_permissions: list[str]
    permission_gaps: list[PermissionGap]
    best_builtin_match: BuiltInRoleMatch | None
    alternative_builtins: list[BuiltInRoleMatch]
    custom_role: CustomRoleDefinition
    reduction_score: float  # 0–100 (% of permissions reduced)
    computed_at: datetime
