from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.auth.deps import CurrentUser, get_current_user, validate_project_access
from app.auth.obo import OboTokenProvider
from app.config import Settings, get_settings
from app.models.project import ScanPhase, ScanRecord
from app.pipelines.ingest_pipeline import IngestPipeline
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.crypto import CryptoService
from app.services.graph_ingest import GraphApiError, GraphIngestService, GraphPermissionError, GraphThrottledError
from app.services.graph_roles import GraphRolesService
from app.services.permission_validator import REQUIRED_PERMISSIONS
from app.services.scan_events import ScanEventBroker, drain_queue, encode_sse

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
    "pim_sessions",
    "access_paths",
]


async def _finalize_failed_scan(
    scan: ScanRecord,
    project: Any,
    repo: CosmosRepo,
    error_message: str,
) -> None:
    scan.status = "failed"
    scan.error_message = error_message
    scan.completed_at = datetime.now(UTC)
    for phase in scan.phases:
        if phase.status == "running":
            phase.status = "failed"
            phase.completed_at = scan.completed_at
    await repo.upsert_scan(scan)

    project.last_scan_at = scan.completed_at
    project.last_scan_status = "failed"
    project.updated_at = datetime.now(UTC)
    await repo.upsert_project(project)


async def _publish_scan_event(
    broker: ScanEventBroker,
    project_id: str,
    *,
    scan_id: str | None,
    type: str,
    message: str,
    level: str = "info",
    phase: str | None = None,
    status: str | None = None,
    items_processed: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    await broker.publish(
        project_id,
        scan_id=scan_id,
        type=type,
        message=message,
        level=level,
        phase=phase,
        status=status,
        items_processed=items_processed,
        details=details,
    )


async def _run_scan_task(
    app: Any,
    repo: CosmosRepo,
    project: Any,
    scan: ScanRecord,
    *,
    full: bool,
    auth_mode: str,
    bearer_token: str | None,
    settings: Settings,
) -> None:
    broker: ScanEventBroker = app.state.scan_event_broker

    async def emit(payload: dict[str, Any]) -> None:
        await _publish_scan_event(
            broker,
            project.id,
            scan_id=scan.id,
            type=payload.get("type", "scan.info"),
            message=payload.get("message", "Scan progress updated."),
            level=payload.get("level", "info"),
            phase=payload.get("phase"),
            status=payload.get("status"),
            items_processed=payload.get("items_processed"),
            details=payload.get("details"),
        )

    try:
        await emit(
            {
                "type": "scan.started",
                "message": f"Started {scan.scan_type} scan using {auth_mode} credentials.",
                "status": "running",
            }
        )

        if auth_mode == "delegated":
            if bearer_token is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing Bearer token",
                )
            obo = OboTokenProvider(settings)
            token_provider = obo.get_token_provider(
                bearer_token, project.target_tenant_id,
            )
            graph = GraphIngestService(
                settings,
                token_provider=token_provider,
                progress_callback=emit,
            )
        else:
            if not project.client_id or not project.encrypted_client_secret:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project has no app credentials configured. Use delegated mode.",
                )
            crypto = CryptoService(settings)
            secret = crypto.decrypt(project.encrypted_client_secret)
            graph = GraphIngestService(
                settings,
                client_id=project.client_id,
                client_secret=secret,
                progress_callback=emit,
            )

        roles_svc = GraphRolesService(graph)
        pipeline = IngestPipeline(repo, graph, roles_svc, progress_callback=emit)
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

        await emit(
            {
                "type": "scan.finished",
                "message": "Scan completed successfully.",
                "status": "completed",
                "details": summary,
            }
        )
    except HTTPException as exc:
        await _finalize_failed_scan(scan, project, repo, str(exc.detail))
        await emit(
            {
                "type": "scan.failed",
                "level": "error",
                "message": str(exc.detail),
                "status": "failed",
            }
        )
    except GraphPermissionError as exc:
        message = "Microsoft Graph denied access for this scan. Verify the configured identity has the required delegated or application permissions."
        await _finalize_failed_scan(scan, project, repo, message)
        logger.warning("Scan forbidden for project %s: %s", project.id, exc)
        await emit(
            {
                "type": "scan.failed",
                "level": "warning",
                "message": message,
                "status": "failed",
            }
        )
    except GraphThrottledError as exc:
        message = "Microsoft Graph throttled this scan after retrying. Please wait and try again."
        await _finalize_failed_scan(scan, project, repo, message)
        logger.warning("Scan throttled for project %s: %s", project.id, exc)
        await emit(
            {
                "type": "scan.failed",
                "level": "warning",
                "message": message,
                "status": "failed",
            }
        )
    except GraphApiError as exc:
        message = "Scan failed due to a Microsoft Graph error. Check backend logs for the upstream failure details."
        await _finalize_failed_scan(scan, project, repo, message)
        logger.error("Graph API error for project %s: %s", project.id, exc)
        await emit(
            {
                "type": "scan.failed",
                "level": "error",
                "message": message,
                "status": "failed",
            }
        )
    except Exception as exc:
        message = "Scan failed due to an internal server error. Check backend logs for details."
        await _finalize_failed_scan(scan, project, repo, message)
        logger.error("Scan failed for project %s: %s", project.id, exc)
        await emit(
            {
                "type": "scan.failed",
                "level": "error",
                "message": message,
                "status": "failed",
            }
        )


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    return auth.removeprefix("Bearer ")


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    project_id: str,
    request: Request,
    full: bool = False,
    auth_mode: str = Query(default="app", pattern="^(app|delegated)$"),
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger a scan using stored app credentials or the user's delegated token."""
    project = await validate_project_access(
        project_id, user, repo, settings, required_role="operator",
    )
    latest_scan = await repo.get_latest_scan(project_id)
    if latest_scan is not None and latest_scan.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already running for this project.",
        )
    bearer_token = _extract_bearer(request) if auth_mode == "delegated" else None

    now = datetime.now(UTC)
    scan = ScanRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        target_tenant_id=project.target_tenant_id,
        scan_type="full" if full else "incremental",
        auth_mode=auth_mode,
        status="running",
        phases=[ScanPhase(name=p) for p in _DEFAULT_PHASES],
        started_at=now,
    )
    await repo.upsert_scan(scan)
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan event streaming is not configured on this backend instance.",
        )
    try:
        await _publish_scan_event(
            broker,
            project_id,
            scan_id=scan.id,
            type="scan.queued",
            message=f"Queued {scan.scan_type} scan using {auth_mode} credentials.",
            status="running",
        )
    except Exception as exc:
        logger.warning("Failed to queue scan event for project %s: %s", project_id, exc)
        await _finalize_failed_scan(
            scan,
            project,
            repo,
            "Scan event streaming is temporarily unavailable. Retry the scan.",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan event streaming is temporarily unavailable. Retry the scan.",
        ) from exc

    task = asyncio.create_task(
        _run_scan_task(
            request.app,
            repo,
            project,
            scan,
            full=full,
            auth_mode=auth_mode,
            bearer_token=bearer_token,
            settings=settings,
        )
    )
    request.app.state.scan_tasks.add(task)
    task.add_done_callback(request.app.state.scan_tasks.discard)

    return {
        "scan_id": scan.id,
        "status": "running",
        "auth_mode": auth_mode,
    }


@router.get("/events")
async def stream_scan_events(
    project_id: str,
    request: Request,
    scan_id: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Stream live scan and action-ingest events for a project as SSE."""
    await validate_project_access(project_id, user, repo, settings)
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan event streaming is not configured on this backend instance.",
        )

    async def event_stream() -> AsyncIterator[bytes]:
        async with broker.subscribe(project_id, scan_id=scan_id) as queue:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield encode_sse(event)
                    if event.get("type") == "stream.error":
                        break
                except asyncio.TimeoutError:
                    yield b": keepalive\n\n"
            await drain_queue(queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=headers,
    )


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


@router.get("/delegated-permissions-check")
async def check_delegated_permissions(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Check what Graph permissions the user would get via OBO delegated flow."""
    project = await validate_project_access(project_id, user, repo, settings)

    if settings.local_mode:
        return {
            "sufficient": True,
            "granted_scopes": list(REQUIRED_PERMISSIONS),
            "missing_scopes": [],
        }

    bearer = _extract_bearer(request)
    obo = OboTokenProvider(settings)
    try:
        graph_token = await obo.get_graph_token(bearer, project.target_tenant_id)
    except RuntimeError as exc:
        return {
            "sufficient": False,
            "granted_scopes": [],
            "missing_scopes": list(REQUIRED_PERMISSIONS),
            "error": str(exc),
        }

    payload = pyjwt.decode(graph_token, options={"verify_signature": False})
    granted_scopes: list[str] = []
    scp = payload.get("scp", "")
    if scp:
        granted_scopes = scp.split(" ")
    roles = payload.get("roles", [])
    if roles:
        granted_scopes.extend(roles)

    missing = [p for p in REQUIRED_PERMISSIONS if p not in granted_scopes]
    return {
        "sufficient": len(missing) == 0,
        "granted_scopes": granted_scopes,
        "missing_scopes": missing,
    }


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
