# backend/app/models/custom_role.py
"""Pydantic v2 model for Entra ID / Azure RBAC custom role definitions."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BuiltinRoleOverlap(BaseModel):
    """Overlap measurement between a custom role and a built-in role."""

    role_name: str
    overlap_pct: float


class CustomRoleProfile(BaseModel):
    """A custom role definition with privilege-analysis metadata."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    role_definition_id: str
    display_name: str
    description: str = ""
    is_enabled: bool = True
    permissions: list[str] = []  # e.g. ["microsoft.directory/users/basic/read"]
    is_overprivileged: bool = False
    has_escalation_paths: bool = False
    assignment_count: int = 0
    overlap_with_builtin: list[BuiltinRoleOverlap] = []
    created_at: datetime | None = None
    last_modified: datetime | None = None
