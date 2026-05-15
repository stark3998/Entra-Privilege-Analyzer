# backend/app/routers/reports.py
"""API endpoints for downloading executive reports."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/reports",
    tags=["reports"],
)


@router.get("/executive")
async def download_executive_report(
    tenant_id: str,
    format: str = Query(default="pdf", pattern="^(pdf|pptx)$"),
    user: CurrentUser = Depends(require_role("Executive", "IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Download an executive report in PDF or PPTX format."""
    validate_tenant_access(tenant_id, user, settings)

    generator = ReportGenerator(repo)

    if format == "pdf":
        content = await generator.generate_executive_pdf(tenant_id)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (f'attachment; filename="executive_report_{tenant_id}.pdf"'),
            },
        )
    elif format == "pptx":
        content = await generator.generate_executive_pptx(tenant_id)
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="executive_report_{tenant_id}.pptx"'
                ),
            },
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Use 'pdf' or 'pptx'.",
        )
