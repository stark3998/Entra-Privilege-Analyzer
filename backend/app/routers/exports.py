# backend/app/routers/exports.py
from __future__ import annotations

import io
import logging
import re
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.export import ExportFormat
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.iac_exporter import IacExporter

logger = logging.getLogger(__name__)

_MAX_BULK_EXPORT = 500

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/exports",
    tags=["exports"],
)

_exporter = IacExporter()


@router.get("/{identity_id}")
async def export_recommendation(
    tenant_id: str,
    identity_id: str,
    format: ExportFormat = Query(default=ExportFormat.TERRAFORM),
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Export an IaC role definition for a single identity."""
    validate_tenant_access(tenant_id, user, settings)

    rec = await repo.get_recommendation(tenant_id, identity_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found — compute recommendations first",
        )

    logger.info(
        "audit.export identity=%s format=%s user=%s",
        identity_id,
        format.value,
        user.oid,
    )

    result = _exporter.export(rec, format)
    return result.model_dump(mode="json")


@router.post("/bulk")
async def bulk_export(
    tenant_id: str,
    format: ExportFormat = Query(default=ExportFormat.TERRAFORM),
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Export IaC definitions for all identities as a zip archive."""
    validate_tenant_access(tenant_id, user, settings)

    items, _ = await repo.list_recommendations(
        tenant_id=tenant_id, offset=0, limit=_MAX_BULK_EXPORT,
    )

    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendations found — compute recommendations first",
        )

    logger.info(
        "audit.bulk_export tenant=%s format=%s count=%d user=%s",
        tenant_id,
        format.value,
        len(items),
        user.oid,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in items:
            result = _exporter.export(rec, format)
            zf.writestr(result.filename, result.content)

    buf.seek(0)
    safe_tenant = re.sub(r"[^a-zA-Z0-9_-]", "", tenant_id)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="roles-{safe_tenant}.zip"'},
    )
