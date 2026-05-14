# backend/app/models/conditional_access.py
"""Pydantic v2 models for Conditional Access policy data from Microsoft Graph API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaPolicyConditionUsers(BaseModel):
    """User/group/role targeting within a CA policy condition."""

    include_users: list[str] = []
    exclude_users: list[str] = []
    include_groups: list[str] = []
    exclude_groups: list[str] = []
    include_roles: list[str] = []
    exclude_roles: list[str] = []


class CaPolicyConditions(BaseModel):
    """Conditions block of a Conditional Access policy."""

    users: CaPolicyConditionUsers = CaPolicyConditionUsers()
    include_applications: list[str] = []
    exclude_applications: list[str] = []
    client_app_types: list[str] = []
    sign_in_risk_levels: list[str] = []
    user_risk_levels: list[str] = []
    include_platforms: list[str] | None = None
    include_locations: list[str] | None = None
    exclude_locations: list[str] | None = None


class CaPolicyGrantControls(BaseModel):
    """Grant controls block of a Conditional Access policy."""

    operator: str = "OR"
    built_in_controls: list[str] = []
    authentication_strength: dict[str, str] | None = None


class ConditionalAccessPolicyRecord(BaseModel):
    """A single Conditional Access policy stored in Cosmos DB."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    display_name: str
    state: str  # "enabled" | "disabled" | "enabledForReportingButNotEnforced"
    conditions: CaPolicyConditions = CaPolicyConditions()
    grant_controls: CaPolicyGrantControls | None = None
    created_at: datetime
    modified_at: datetime
