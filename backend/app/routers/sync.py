# backend/app/routers/sync.py
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.pipelines.ingest_pipeline import IngestPipeline
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.graph_ingest import GraphIngestService
from app.services.graph_roles import GraphRolesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{tenant_id}/sync", tags=["sync"])


@router.post("/trigger")
async def trigger_sync(
    tenant_id: str,
    full: bool = False,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger a full or incremental sync for the tenant."""
    validate_tenant_access(tenant_id, user, settings)

    if not settings.azure_client_id or not settings.azure_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph API credentials not configured",
        )

    graph = GraphIngestService(settings)
    roles_svc = GraphRolesService(graph)
    pipeline = IngestPipeline(repo, graph, roles_svc)

    summary = await pipeline.run(tenant_id, full_sync=full)
    return summary


@router.get("/status")
async def get_sync_status(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return sync state for all sync types."""
    validate_tenant_access(tenant_id, user, settings)

    audit_state = await repo.get_sync_state(tenant_id, "audit_logs")
    signin_state = await repo.get_sync_state(tenant_id, "sign_in_logs")

    return {
        "tenant_id": tenant_id,
        "audit_logs": audit_state,
        "sign_in_logs": signin_state,
    }
