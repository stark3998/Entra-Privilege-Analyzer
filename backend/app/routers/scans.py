from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.deps import CurrentUser, get_current_user, validate_project_access
from app.config import Settings, get_settings
from app.models.project import ScanPhase, ScanRecord
from app.pipelines.ingest_pipeline import IngestPipeline
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.crypto import CryptoService
from app.services.graph_ingest import GraphIngestService
from app.services.graph_roles import GraphRolesService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/scans",
    tags=["scans"],
)

_DEFAULT_PHASES = [
    "audit_logs",
    "sign_in_logs",
    "role_assignments",
    "identity_profiles",
    "action_events",
]


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    project_id: str,
    full: bool = False,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger a scan using the project's stored credentials."""
    project = await validate_project_access(
        project_id, user, repo, settings, required_role="operator",
    )

    now = datetime.now(UTC)
    scan = ScanRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        target_tenant_id=project.target_tenant_id,
        scan_type="full" if full else "incremental",
        status="running",
        phases=[ScanPhase(name=p) for p in _DEFAULT_PHASES],
        started_at=now,
    )
    await repo.upsert_scan(scan)

    try:
        crypto = CryptoService(settings)
        secret = crypto.decrypt(project.encrypted_client_secret)

        graph = GraphIngestService(
            settings,
            client_id=project.client_id,
            client_secret=secret,
        )
        roles_svc = GraphRolesService(graph)
        pipeline = IngestPipeline(repo, graph, roles_svc)
        summary = await pipeline.run(
            project.target_tenant_id,
            full_sync=full,
            scan_record=scan,
        )

        scan.status = "completed"
        scan.completed_at = datetime.now(UTC)
        await repo.upsert_scan(scan)

        project.last_scan_at = scan.completed_at
        project.last_scan_status = "completed"
        if "identities_processed" in summary:
            project.identity_count = summary["identities_processed"]
        project.updated_at = datetime.now(UTC)
        await repo.upsert_project(project)

        return {
            "scan_id": scan.id,
            "status": "completed",
            "summary": summary,
        }
    except Exception as exc:
        scan.status = "failed"
        scan.error_message = str(exc)
        scan.completed_at = datetime.now(UTC)
        await repo.upsert_scan(scan)

        project.last_scan_at = scan.completed_at
        project.last_scan_status = "failed"
        project.updated_at = datetime.now(UTC)
        await repo.upsert_project(project)

        logger.error("Scan failed for project %s: %s", project_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {exc}",
        ) from exc


@router.get("")
async def list_scans(
    project_id: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List scan history for a project."""
    await validate_project_access(project_id, user, repo, settings)
    offset = (page - 1) * size
    items, total = await repo.list_scans(project_id, offset, size)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/latest")
async def get_latest_scan(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get the most recent scan for a project."""
    await validate_project_access(project_id, user, repo, settings)
    scan = await repo.get_latest_scan(project_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="No scans found")
    return scan.model_dump(mode="json")


@router.get("/{scan_id}")
async def get_scan(
    project_id: str,
    scan_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get scan detail with phase breakdown."""
    await validate_project_access(project_id, user, repo, settings)
    scan = await repo.get_scan(project_id, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan.model_dump(mode="json")
