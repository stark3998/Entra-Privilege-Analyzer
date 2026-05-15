from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from datetime import timedelta
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

_SCAN_HEARTBEAT_INTERVAL_SECONDS = 30
_SCAN_LEASE_SECONDS = 120
_STALE_SCAN_MESSAGE = "Scan abandoned after backend restart or task loss."
_CANCELLED_SCAN_MESSAGE = "Scan interrupted by backend shutdown or redeploy before completion."
_STREAM_OPEN_FRAME = b": stream-open" + b" " * 2048 + b"\n\n"

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
    *,
    owner_instance_id: str | None = None,
) -> None:
    scan.status = "failed"
    scan.error_message = error_message
    scan.completed_at = datetime.now(UTC)
    _clear_scan_lease(scan)
    for phase in scan.phases:
        if phase.status in {"pending", "running"}:
            phase.status = "failed"
            phase.completed_at = scan.completed_at
    await repo.upsert_scan(scan)
    if owner_instance_id is None:
        project.last_scan_at = scan.completed_at
        project.last_scan_status = "failed"
        project.updated_at = datetime.now(UTC)
        await repo.upsert_project(project)
        return
    released_project = await repo.release_project_scan_lease(
        project.id,
        scan.id,
        owner_instance_id,
        scan.completed_at,
        "failed",
    )
    if released_project is not None:
        project.last_scan_at = released_project.last_scan_at
        project.last_scan_status = released_project.last_scan_status
        project.updated_at = released_project.updated_at


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


def _build_scan_snapshot_event(project_id: str, scan: ScanRecord) -> dict[str, Any]:
    now = datetime.now(UTC)
    running_phase = next((phase.name for phase in scan.phases if phase.status == "running"), None)
    if scan.status in {"running", "queued"}:
        message = f"{scan.scan_type.title()} scan is currently {scan.status}."
    elif scan.status == "completed":
        message = f"{scan.scan_type.title()} scan completed."
    else:
        message = f"{scan.scan_type.title()} scan last ended with status {scan.status}."

    return {
        "id": f"{project_id}:{scan.id}:snapshot:{now.timestamp()}",
        "type": "scan.snapshot",
        "message": message,
        "project_id": project_id,
        "scan_id": scan.id,
        "level": "info" if scan.status != "failed" else "error",
        "phase": running_phase,
        "status": scan.status,
        "items_processed": None,
        "timestamp": now.isoformat(),
        "details": {
            "snapshot": True,
            "scan_type": scan.scan_type,
            "auth_mode": scan.auth_mode,
            "started_at": scan.started_at.isoformat(),
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            "error_message": scan.error_message,
            "phases": [phase.model_dump(mode="json") for phase in scan.phases],
        },
    }


def _stamp_scan_lease(scan: ScanRecord, instance_id: str, now: datetime) -> None:
    scan.owner_instance_id = instance_id
    scan.heartbeat_at = now
    scan.lease_expires_at = now + timedelta(seconds=_SCAN_LEASE_SECONDS)


def _clear_scan_lease(scan: ScanRecord) -> None:
    scan.owner_instance_id = None
    scan.heartbeat_at = None
    scan.lease_expires_at = None


def _scan_lease_is_active(scan: ScanRecord, now: datetime) -> bool:
    if scan.status not in {"queued", "running"}:
        return False
    if scan.lease_expires_at is None:
        return True
    return scan.lease_expires_at > now


async def _heartbeat_scan(
    repo: CosmosRepo,
    scan: ScanRecord,
    *,
    instance_id: str,
    stop_event: asyncio.Event,
    lease_lost_event: asyncio.Event,
    worker_task: asyncio.Task[Any] | None,
    progress_callback: Any | None = None,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_SCAN_HEARTBEAT_INTERVAL_SECONDS)
            break
        except asyncio.TimeoutError:
            if scan.status != "running":
                break
            now = datetime.now(UTC)
            if not await repo.renew_project_scan_lease(
                scan.project_id,
                scan.id,
                instance_id,
                now,
                now + timedelta(seconds=_SCAN_LEASE_SECONDS),
            ):
                logger.warning("Scan %s for project %s lost its lease; stopping worker heartbeat", scan.id, scan.project_id)
                lease_lost_event.set()
                if worker_task is not None:
                    worker_task.cancel()
                break
            _stamp_scan_lease(scan, instance_id, now)
            await repo.upsert_scan(scan)
            if progress_callback is not None:
                running_phase = next((phase.name for phase in scan.phases if phase.status == "running"), None)
                phase_label = running_phase.replace("_", " ") if running_phase else "current phase"
                await progress_callback(
                    {
                        "type": "scan.heartbeat",
                        "message": f"Scan still running in {phase_label}.",
                        "phase": running_phase,
                        "status": scan.status,
                    }
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
    instance_id = app.state.instance_id
    heartbeat_stop = asyncio.Event()
    lease_lost = asyncio.Event()
    worker_task = asyncio.current_task()

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

    heartbeat_task = asyncio.create_task(
        _heartbeat_scan(
            repo,
            scan,
            instance_id=instance_id,
            stop_event=heartbeat_stop,
            lease_lost_event=lease_lost,
            worker_task=worker_task,
            progress_callback=emit,
        )
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

        if not await repo.has_project_scan_lease(
            project.id,
            scan.id,
            instance_id,
            datetime.now(UTC),
        ):
            logger.warning("Scan %s for project %s lost its lease before completion; skipping final write", scan.id, project.id)
            return

        _clear_scan_lease(scan)
        scan.status = "completed"
        scan.completed_at = datetime.now(UTC)
        await repo.upsert_scan(scan)
        released_project = await repo.release_project_scan_lease(
            project.id,
            scan.id,
            instance_id,
            scan.completed_at,
            "completed",
            identity_count=summary.get("identities_processed"),
        )
        if released_project is not None:
            project.last_scan_at = released_project.last_scan_at
            project.last_scan_status = released_project.last_scan_status
            project.identity_count = released_project.identity_count
            project.updated_at = released_project.updated_at

        await emit(
            {
                "type": "scan.finished",
                "message": "Scan completed successfully.",
                "status": "completed",
                "details": summary,
            }
        )
    except HTTPException as exc:
        await _finalize_failed_scan(scan, project, repo, str(exc.detail), owner_instance_id=instance_id)
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
        await _finalize_failed_scan(scan, project, repo, message, owner_instance_id=instance_id)
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
        await _finalize_failed_scan(scan, project, repo, message, owner_instance_id=instance_id)
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
        await _finalize_failed_scan(scan, project, repo, message, owner_instance_id=instance_id)
        logger.error("Graph API error for project %s: %s", project.id, exc)
        await emit(
            {
                "type": "scan.failed",
                "level": "error",
                "message": message,
                "status": "failed",
            }
        )
    except asyncio.CancelledError:
        if lease_lost.is_set():
            scan.status = "failed"
            scan.error_message = _STALE_SCAN_MESSAGE
            scan.completed_at = datetime.now(UTC)
            _clear_scan_lease(scan)
            for phase in scan.phases:
                if phase.status in {"pending", "running"}:
                    phase.status = "failed"
                    phase.completed_at = scan.completed_at
            await repo.upsert_scan(scan)
            logger.warning("Scan %s for project %s stopped after lease loss", scan.id, project.id)
            return
        await _finalize_failed_scan(
            scan,
            project,
            repo,
            _CANCELLED_SCAN_MESSAGE,
            owner_instance_id=instance_id,
        )
        raise
    except Exception as exc:
        message = "Scan failed due to an internal server error. Check backend logs for details."
        await _finalize_failed_scan(scan, project, repo, message, owner_instance_id=instance_id)
        logger.error("Scan failed for project %s: %s", project.id, exc)
        await emit(
            {
                "type": "scan.failed",
                "level": "error",
                "message": message,
                "status": "failed",
            }
        )
    finally:
        heartbeat_stop.set()
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


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
    now = datetime.now(UTC)
    if latest_scan is not None and latest_scan.status in {"queued", "running"}:
        if _scan_lease_is_active(latest_scan, now):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A scan is already running for this project.",
            )
    bearer_token = _extract_bearer(request) if auth_mode == "delegated" else None
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
    _stamp_scan_lease(scan, request.app.state.instance_id, now)
    leased_project = await repo.try_acquire_project_scan_lease(
        project_id,
        scan.id,
        request.app.state.instance_id,
        now,
        scan.lease_expires_at,
    )
    if leased_project is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already running for this project.",
        )
    project = leased_project
    try:
        if latest_scan is not None and latest_scan.status in {"queued", "running"} and not _scan_lease_is_active(latest_scan, now):
            latest_scan.status = "failed"
            latest_scan.error_message = _STALE_SCAN_MESSAGE
            latest_scan.completed_at = now
            _clear_scan_lease(latest_scan)
            for phase in latest_scan.phases:
                if phase.status in {"pending", "running"}:
                    phase.status = "failed"
                    phase.completed_at = now
            await repo.upsert_scan(latest_scan)
        await repo.upsert_scan(scan)
    except Exception:
        await repo.clear_project_scan_lease(project_id, scan.id, request.app.state.instance_id)
        raise
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is None:
        await repo.clear_project_scan_lease(project_id, scan.id, request.app.state.instance_id)
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
            owner_instance_id=request.app.state.instance_id,
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
    request.app.state.scan_tasks[scan.id] = task
    task.add_done_callback(lambda t, sid=scan.id: request.app.state.scan_tasks.pop(sid, None))

    return {
        "scan_id": scan.id,
        "status": "running",
        "auth_mode": auth_mode,
    }


@router.get("/events/poll")
async def poll_scan_events(
    project_id: str,
    request: Request,
    scan_id: str | None = Query(default=None),
    after: str | None = Query(default=None, description="ISO timestamp cursor; only events newer than this are returned"),
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Poll for buffered scan events since a given cursor.

    Drop-in replacement for the SSE ``/events`` endpoint when running behind
    proxies (e.g. Azure Container Apps Envoy) that buffer streaming responses.
    The frontend polls this every ~2 seconds instead of keeping an SSE
    connection open.
    """
    await validate_project_access(project_id, user, repo, settings)
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan event streaming is not configured on this backend instance.",
        )

    events: list[dict[str, Any]] = []

    # When no cursor is provided, lead with a snapshot of the latest scan so
    # the client gets phase state without waiting for a live event.
    latest_scan = await repo.get_latest_scan(project_id)
    if after is None and latest_scan is not None and (scan_id is None or latest_scan.id == scan_id):
        events.append(_build_scan_snapshot_event(project_id, latest_scan))

    buffered = broker.get_events_after(project_id, scan_id=scan_id, after_timestamp=after)
    events.extend(buffered)

    # Determine the cursor for the next poll — the timestamp of the last event
    cursor: str | None = None
    if events:
        cursor = events[-1].get("timestamp")

    # Include the scan status so the frontend knows when to stop polling.
    scan_status: str | None = None
    if latest_scan is not None and (scan_id is None or latest_scan.id == scan_id):
        scan_status = latest_scan.status

    return {
        "events": events,
        "cursor": cursor,
        "scan_status": scan_status,
        "has_more": False,
    }


@router.post("/{scan_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_scan(
    project_id: str,
    scan_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Cancel a running scan."""
    await validate_project_access(project_id, user, repo, settings, required_role="operator")
    scan = await repo.get_scan(project_id, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status not in {"queued", "running"}:
        raise HTTPException(status_code=400, detail=f"Scan is already {scan.status}")

    # Cancel the asyncio task if it's running on this instance
    task = request.app.state.scan_tasks.get(scan_id)
    if task is not None and not task.done():
        task.cancel()

    # Mark the scan as failed/cancelled in Cosmos
    now = datetime.now(UTC)
    scan.status = "failed"
    scan.error_message = "Scan cancelled by user."
    scan.completed_at = now
    _clear_scan_lease(scan)
    for phase in scan.phases:
        if phase.status in {"pending", "running"}:
            phase.status = "failed"
            phase.completed_at = now
    await repo.upsert_scan(scan)

    # Release the project scan lease
    instance_id = request.app.state.instance_id
    await repo.release_project_scan_lease(
        project_id, scan_id, instance_id, now, "failed",
    )

    # Publish cancellation event
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is not None:
        await _publish_scan_event(
            broker, project_id, scan_id=scan_id,
            type="scan.cancelled", message="Scan cancelled by user.",
            level="warning", status="failed",
        )

    return {"scan_id": scan_id, "status": "failed", "message": "Scan cancelled."}


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
    latest_scan = await repo.get_latest_scan(project_id)
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan event streaming is not configured on this backend instance.",
        )

    async def event_stream() -> AsyncIterator[bytes]:
        async with broker.subscribe(project_id, scan_id=scan_id) as queue:
            yield _STREAM_OPEN_FRAME
            if latest_scan is not None and (scan_id is None or latest_scan.id == scan_id):
                yield encode_sse(_build_scan_snapshot_event(project_id, latest_scan))
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield encode_sse(event)
                    if event.get("type") == "stream.error":
                        break
                except asyncio.TimeoutError:
                    yield b": keepalive" + b" " * 2048 + b"\n\n"
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
