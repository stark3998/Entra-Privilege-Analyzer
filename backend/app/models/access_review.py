# backend/app/models/access_review.py
"""Pydantic v2 model for Entra ID access review definitions."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccessReviewDefinition(BaseModel):
    """An access review definition synced from Entra ID."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    display_name: str
    status: str  # Initializing|NotStarted|Starting|InProgress|Completing|Completed|AutoReviewing|AutoReviewed
    scope_query: str = ""
    scope_type: str = ""  # group | role | accessPackage
    target_resource_id: str | None = None
    reviewers: list[str] = []
    recurrence_pattern: str | None = None
    last_instance_end: datetime | None = None
    created_at: datetime | None = None
