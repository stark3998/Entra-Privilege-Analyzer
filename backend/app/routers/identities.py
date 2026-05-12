# backend/app/routers/identities.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import CurrentUser, get_current_user, validate_tenant_access
from app.config import Settings, get_settings
from app.services.cosmos import CosmosRepo, get_cosmos_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/identities", tags=["identities"])


@router.get("")
async def list_identities(
    tenant_id: str,
    type: str | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 50,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List identity profiles for a tenant with optional type filter and search."""
    validate_tenant_access(tenant_id, user, settings)

    offset = (page - 1) * size
    items, total = await repo.list_identities(
        tenant_id=tenant_id,
        identity_type=type,
        search=search,
        offset=offset,
        limit=size,
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{identity_id}")
async def get_identity(
    tenant_id: str,
    identity_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get a single identity profile by ID."""
    validate_tenant_access(tenant_id, user, settings)

    profile = await repo.get_identity(tenant_id, identity_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Identity {identity_id} not found",
        )
    return profile.model_dump(mode="json")
