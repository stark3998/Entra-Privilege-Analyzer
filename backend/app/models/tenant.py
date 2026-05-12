# backend/app/models/tenant.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TenantConfig(BaseModel):
    """Tenant configuration stored in Cosmos DB."""

    id: str  # same as tenant_id — Cosmos document id
    tenant_id: str
    display_name: str
    sync_schedule_hours: int = 6
    baseline_window_days: int = 30
    created_at: datetime
    updated_at: datetime
