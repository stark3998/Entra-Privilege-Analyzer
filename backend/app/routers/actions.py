# backend/app/routers/actions.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.services.cosmos import CosmosRepo, get_cosmos_repo

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/identities/{identity_id}/actions",
    tags=["actions"],
)


@router.get("")
async def list_actions(
    tenant_id: str,
    identity_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    size: int = 50,
    user: CurrentUser = Depends(require_role("SecurityEngineer", "IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List action events for a specific identity with optional time range filter."""
    validate_tenant_access(tenant_id, user, settings)

    offset = (page - 1) * size
    items, total = await repo.list_actions(
        tenant_id=tenant_id,
        identity_id=identity_id,
        start=start,
        end=end,
        offset=offset,
        limit=size,
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "size": size,
    }
