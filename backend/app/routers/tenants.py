# backend/app/routers/tenants.py
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, get_current_user, require_role
from app.models.tenant import TenantConfig
from app.services.cosmos import CosmosRepo, get_cosmos_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("/me")
async def get_my_tenant(
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str | list[str]]:
    """Return the authenticated user's tenant info and roles."""
    return {
        "tenant_id": user.tid,
        "name": user.name,
        "email": user.email,
        "roles": user.roles,
    }


@router.post("/onboard")
async def onboard_tenant(
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
) -> dict[str, Any]:
    """Register the user's tenant and create initial configuration.

    If the tenant is already onboarded, returns the existing config.
    """
    existing = await repo.get_tenant_config(user.tid)
    if existing is not None:
        return existing.model_dump(mode="json")

    now = datetime.now(UTC)
    config = TenantConfig(
        id=user.tid,
        tenant_id=user.tid,
        display_name=f"Tenant {user.tid}",
        sync_schedule_hours=6,
        baseline_window_days=30,
        created_at=now,
        updated_at=now,
    )

    saved = await repo.upsert_tenant_config(config)
    logger.info("Tenant onboarded: %s", user.tid)
    return saved.model_dump(mode="json")
