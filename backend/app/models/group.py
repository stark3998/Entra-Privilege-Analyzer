# backend/app/models/group.py
"""Pydantic v2 model for Entra ID group profiles."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GroupOwner(BaseModel):
    """Structured owner record for a group."""

    id: str
    display_name: str | None = None
    user_principal_name: str | None = None
    owner_type: str = "User"


class GroupProfile(BaseModel):
    """An Entra ID security or Microsoft 365 group with role-assignment metadata."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    display_name: str
    is_role_assignable: bool = False
    is_dynamic: bool = False
    membership_rule: str | None = None
    security_enabled: bool = True
    member_count: int = 0
    transitive_member_count: int = 0
    owner_count: int = 0
    owners: list[GroupOwner] = []
    roles_assigned: list[str] = []
    created_at: datetime | None = None
