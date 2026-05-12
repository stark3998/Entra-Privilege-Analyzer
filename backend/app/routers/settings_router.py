# backend/app/routers/settings_router.py
"""API endpoints for tenant settings management."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.tenant import TenantConfig
from app.services.cosmos import CosmosRepo, get_cosmos_repo

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/settings",
    tags=["settings"],
)


class TenantSettingsUpdate(BaseModel):
    """Payload for updating tenant settings."""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    sync_schedule_hours: int | None = Field(default=None, ge=1, le=168)
    baseline_window_days: int | None = Field(default=None, ge=7, le=365)


@router.get("")
async def get_tenant_settings(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return the current tenant configuration."""
    validate_tenant_access(tenant_id, user, settings)

    config = await repo.get_tenant_config(tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant configuration not found",
        )
    return config.model_dump(mode="json")


@router.put("")
async def update_tenant_settings(
    tenant_id: str,
    body: TenantSettingsUpdate,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Update tenant configuration (sync schedule, baseline window)."""
    validate_tenant_access(tenant_id, user, settings)

    config = await repo.get_tenant_config(tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant configuration not found",
        )

    if body.display_name is not None:
        config.display_name = body.display_name
    if body.sync_schedule_hours is not None:
        config.sync_schedule_hours = body.sync_schedule_hours
    if body.baseline_window_days is not None:
        config.baseline_window_days = body.baseline_window_days
    config.updated_at = datetime.now(UTC)

    updated = await repo.upsert_tenant_config(config)

    logger.info(
        "audit.settings.update tenant=%s user=%s changes=%s",
        tenant_id,
        user.oid,
        body.model_dump(exclude_none=True),
    )

    return updated.model_dump(mode="json")
