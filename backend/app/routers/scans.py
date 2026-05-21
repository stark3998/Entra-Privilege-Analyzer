from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.auth.deps import CurrentUser, get_current_user, validate_project_access
from app.auth.obo import OboTokenProvider
from app.config import Settings, get_settings
from app.models.project import ScanPhase, ScanRecord
from app.services.master_repo import MasterRepo, get_master_repo
from app.services.project_repo import ProjectRepo
from app.services.project_repo_cache import ProjectRepoCache
from app.services.crypto import CryptoService
from app.services.permission_validator import REQUIRED_PERMISSIONS
from app.services.scan_events import ScanEventBroker, drain_queue, encode_sse

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 3
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
]


# ------------------------------------------------------------------
# Durable Functions history → phase mapping
# ------------------------------------------------------------------

_ACTIVITY_PHASE_MAP: dict[str, str] = {
    "fetch_audit_log_page_activity": "audit_logs",
    "fetch_sign_in_log_page_activity": "sign_in_logs",
    "fetch_users_page_activity": "directory",
    "fetch_sps_page_activity": "directory",
    "fetch_role_assignments_activity": "directory",
    "process_identity_batch_activity": "identity_profiles",
}

_SUB_ORCH_PHASE_MAP: dict[str, str] = {
    "orchestrate_audit_logs": "audit_logs",
    "orchestrate_sign_in_logs": "sign_in_logs",
    "orchestrate_users": "directory",
    "orchestrate_service_principals": "directory",
    "orchestrate_role_assignments": "directory",
}

_SKIP_ACTIVITIES = {"update_scan_phase_activity", "finalize_scan_activity"}

_RELEVANT_EVENT_TYPES = {
    "TaskCompleted",
    "SubOrchestrationInstanceCompleted",
    "TaskFailed",
    "SubOrchestrationInstanceFailed",
}

_FRIENDLY_NAMES: dict[str, str] = {
    "fetch_audit_log_page_activity": "Audit logs page",
    "fetch_sign_in_log_page_activity": "Sign-in logs page",
    "fetch_users_page_activity": "Users page",
    "fetch_sps_page_activity": "Service principals page",
    "fetch_role_assignments_activity": "Role assignments",
    "process_identity_batch_activity": "Identity batch",
    "orchestrate_audit_logs": "Audit logs collection",
    "orchestrate_sign_in_logs": "Sign-in logs collection",
    "orchestrate_users": "Users collection",
    "orchestrate_service_principals": "Service principals collection",
    "orchestrate_role_assignments": "Role assignments collection",
}


# ------------------------------------------------------------------
# Function App dispatch helpers
# ------------------------------------------------------------------

async def _start_function_app_scan(
    settings: Settings,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """POST to the function app's start_scan endpoint. Returns the management URLs."""
    url = f"{settings.scan_function_app_url}/api/start_scan"
    headers = {"x-functions-key": settings.scan_function_key}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code >= 400:
            raise RuntimeError(f"Function app returned {resp.status_code}: {resp.text}")
        return resp.json()


async def _terminate_orchestration(settings: Settings, instance_id: str) -> None:
    """Send a terminate request to the Durable Functions instance."""
    url = f"{settings.scan_function_app_url}/runtime/webhooks/durabletask/instances/{instance_id}/terminate"
    params = {"reason": "Cancelled by user", "taskHub": "EntraPermScanHub"}
    headers = {"x-functions-key": settings.scan_function_key}

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, params=params, headers=headers)
        if resp.status_code >= 400:
            logger.warning("Terminate request failed for %s: %s %s", instance_id, resp.status_code, resp.text)


async def _poll_orchestration_status(
    app: Any,
    repo: MasterRepo,
    project_id: str,
    scan_id: str,
    status_uri: str,
    function_key: str,
) -> None:
    """Poll orchestration status + history and relay per-activity events to the broker."""
    broker: ScanEventBroker = app.state.scan_event_broker
    parsed_status_uri = urlparse(status_uri)
    status_query = parse_qs(parsed_status_uri.query)
    has_embedded_code = bool(status_query.get("code"))
    headers = {} if has_embedded_code else {"x-functions-key": function_key}
    last_message: str | None = None
    last_history_index: int = 0
    history_uri = status_uri + "&showHistory=true&showHistoryOutput=true"

    try:
        while True:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(history_uri, headers=headers)
                    if resp.status_code >= 400:
                        logger.warning("Status poll failed: %s", resp.status_code)
                        continue
                    data = resp.json()
            except Exception as exc:
                logger.warning("Status poll error for scan %s: %s", scan_id, exc)
                continue

            runtime_status = data.get("runtimeStatus", "")
            custom_status = data.get("customStatus") or {}

            # Emit high-level orchestrator status changes
            message = custom_status.get("message", f"Orchestration {runtime_status}")
            if message != last_message and broker is not None:
                step = custom_status.get("step", runtime_status.lower())
                await broker.publish(
                    project_id,
                    scan_id=scan_id,
                    type="scan.progress",
                    message=message,
                    level="info",
                    phase=step,
                    status="running" if runtime_status == "Running" else runtime_status.lower(),
                )
                last_message = message

            # Parse per-activity events from orchestration history
            if broker is not None:
                history_events = data.get("historyEvents") or []
                new_events = history_events[last_history_index:]
                for idx, hist in enumerate(new_events):
                    global_idx = last_history_index + idx
                    await _emit_history_event(broker, project_id, scan_id, hist, global_idx)
                last_history_index = len(history_events)

            if runtime_status in ("Completed", "Failed", "Terminated"):
                scan = await repo.get_scan(project_id, scan_id)
                if scan is not None and scan.status in ("queued", "running"):
                    now = datetime.now(UTC)
                    if runtime_status == "Completed":
                        scan.status = "completed"
                        scan.completed_at = now
                    else:
                        scan.status = "failed"
                        scan.error_message = custom_status.get("message", f"Orchestration {runtime_status}")
                        scan.completed_at = now
                        for phase in scan.phases:
                            if phase.status in ("pending", "running"):
                                phase.status = "failed"
                                phase.completed_at = now
                    scan.owner_instance_id = None
                    scan.heartbeat_at = None
                    scan.lease_expires_at = None
                    await repo.upsert_scan(scan)

                if broker is not None:
                    event_type = "scan.finished" if runtime_status == "Completed" else "scan.failed"
                    await broker.publish(
                        project_id,
                        scan_id=scan_id,
                        type=event_type,
                        message=message,
                        level="info" if runtime_status == "Completed" else "error",
                        status="completed" if runtime_status == "Completed" else "failed",
                    )
                break

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("Poll loop crashed for scan %s: %s", scan_id, exc)


async def _emit_history_event(
    broker: ScanEventBroker,
    project_id: str,
    scan_id: str,
    hist: dict[str, Any],
    index: int,
) -> None:
    """Parse a single Durable Functions history event and publish to the broker."""
    event_type = hist.get("EventType", "")
    if event_type not in _RELEVANT_EVENT_TYPES:
        return

    func_name = hist.get("FunctionName", "")
    if func_name in _SKIP_ACTIVITIES or not func_name:
        return

    phase = _ACTIVITY_PHASE_MAP.get(func_name) or _SUB_ORCH_PHASE_MAP.get(func_name)
    if not phase:
        return

    is_failure = event_type in ("TaskFailed", "SubOrchestrationInstanceFailed")
    friendly = _FRIENDLY_NAMES.get(func_name, func_name)

    result: dict[str, Any] = {}
    if not is_failure:
        raw = hist.get("Result", "")
        try:
            result = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            result = {}

    has_error = is_failure or bool(result.get("error"))
    level = "error" if has_error else "info"
    items = result.get("count") or result.get("processed")
    timestamp = hist.get("Timestamp", datetime.now(UTC).isoformat())

    if is_failure:
        reason = hist.get("Reason", "Unknown error")
        msg = f"{friendly} failed: {reason}"
    elif has_error:
        msg = f"{friendly} error: {result['error']}"
    elif items is not None:
        msg = f"{friendly} completed: {items} items"
    else:
        msg = f"{friendly} completed"

    await broker.publish(
        project_id,
        scan_id=scan_id,
        type="scan.activity",
        message=msg,
        level=level,
        phase=phase,
        status="running",
        items_processed=items,
        details=result if result else None,
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

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


async def _get_project_repo(request: Request, project_id: str, user: CurrentUser, repo: MasterRepo, settings: Settings) -> ProjectRepo:
    project = await validate_project_access(project_id, user, repo, settings)
    cache: ProjectRepoCache = request.app.state.project_repo_cache
    return await cache.get_repo(project.database_name)


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    return auth.removeprefix("Bearer ")


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    project_id: str,
    request: Request,
    full: bool = False,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger a scan by dispatching to the Azure Durable Functions app."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="operator",
    )

    if not settings.scan_function_app_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan function app is not configured.",
        )

    latest_scan = await repo.get_latest_scan(project_id)
    now = datetime.now(UTC)
    if latest_scan is not None and latest_scan.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already running for this project.",
        )

    if not project.client_id or not project.encrypted_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no app credentials configured.",
        )

    crypto = CryptoService(settings)
    client_secret = crypto.decrypt(project.encrypted_client_secret)

    scan = ScanRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        target_tenant_id=project.target_tenant_id,
        scan_type="full" if full else "incremental",
        auth_mode="app",
        status="running",
        phases=[ScanPhase(name=p) for p in _DEFAULT_PHASES],
        started_at=now,
    )

    cosmos_database = project.database_name
    function_payload = {
        "tenant_id": project.target_tenant_id,
        "client_id": project.client_id,
        "client_secret": client_secret,
        "project_id": project_id,
        "scan_id": scan.id,
        "cosmos_endpoint": settings.cosmos_endpoint,
        "cosmos_key": settings.cosmos_key,
        "cosmos_database": cosmos_database,
        "cosmos_master_database": settings.cosmos_master_database,
        "graph_api_version": settings.graph_api_version,
    }

    try:
        result = await _start_function_app_scan(settings, function_payload)
    except Exception as exc:
        logger.error("Failed to start function app scan: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to start scan orchestration. Check function app availability.",
        ) from exc

    scan.orchestration_instance_id = result.get("id")
    scan.orchestration_status_uri = result.get("statusQueryGetUri")
    await repo.upsert_scan(scan)

    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is not None:
        await _publish_scan_event(
            broker,
            project_id,
            scan_id=scan.id,
            type="scan.queued",
            message=f"Queued {scan.scan_type} scan.",
            status="running",
        )

    if scan.orchestration_status_uri:
        task = asyncio.create_task(
            _poll_orchestration_status(
                request.app,
                repo,
                project_id,
                scan.id,
                scan.orchestration_status_uri,
                settings.scan_function_key,
            )
        )
        request.app.state.scan_tasks[scan.id] = task
        task.add_done_callback(lambda t, sid=scan.id: request.app.state.scan_tasks.pop(sid, None))

    return {
        "scan_id": scan.id,
        "status": "running",
        "auth_mode": "app",
    }


@router.get("/events/poll")
async def poll_scan_events(
    project_id: str,
    request: Request,
    scan_id: str | None = Query(default=None),
    after: str | None = Query(
        default=None, description="ISO timestamp cursor; only events newer than this are returned"
    ),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Poll for buffered scan events since a given cursor."""
    await validate_project_access(project_id, user, repo, settings)
    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan event streaming is not configured on this backend instance.",
        )

    events: list[dict[str, Any]] = []

    latest_scan = await repo.get_latest_scan(project_id)
    if after is None and latest_scan is not None and (scan_id is None or latest_scan.id == scan_id):
        events.append(_build_scan_snapshot_event(project_id, latest_scan))

    buffered = broker.get_events_after(project_id, scan_id=scan_id, after_timestamp=after)
    events.extend(buffered)

    # Deduplicate by id and sort by timestamp
    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for evt in events:
        evt_id = evt.get("id")
        if evt_id and evt_id in seen_ids:
            continue
        if evt_id:
            seen_ids.add(evt_id)
        deduped.append(evt)
    deduped.sort(key=lambda e: e.get("timestamp", ""))

    cursor: str | None = None
    if deduped:
        cursor = deduped[-1].get("timestamp")

    scan_status: str | None = None
    if latest_scan is not None and (scan_id is None or latest_scan.id == scan_id):
        scan_status = latest_scan.status

    return {
        "events": deduped,
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
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Cancel a running scan by terminating its Durable Functions orchestration."""
    await validate_project_access(project_id, user, repo, settings, required_role="operator")
    scan = await repo.get_scan(project_id, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status not in {"queued", "running"}:
        raise HTTPException(status_code=400, detail=f"Scan is already {scan.status}")

    if scan.orchestration_instance_id:
        await _terminate_orchestration(settings, scan.orchestration_instance_id)

    poll_task = request.app.state.scan_tasks.get(scan_id)
    if poll_task is not None and not poll_task.done():
        poll_task.cancel()

    now = datetime.now(UTC)
    scan.status = "failed"
    scan.error_message = "Scan cancelled by user."
    scan.completed_at = now
    scan.owner_instance_id = None
    scan.heartbeat_at = None
    scan.lease_expires_at = None
    for phase in scan.phases:
        if phase.status in {"pending", "running"}:
            phase.status = "failed"
            phase.completed_at = now
    await repo.upsert_scan(scan)

    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is not None:
        await _publish_scan_event(
            broker,
            project_id,
            scan_id=scan_id,
            type="scan.cancelled",
            message="Scan cancelled by user.",
            level="warning",
            status="failed",
        )

    return {"scan_id": scan_id, "status": "failed", "message": "Scan cancelled."}


@router.post("/{scan_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_scan(
    project_id: str,
    scan_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Resume a failed scan by starting a new function app orchestration."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="operator",
    )

    if not settings.scan_function_app_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan function app is not configured.",
        )

    failed_scan = await repo.get_scan(project_id, scan_id)
    if failed_scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if failed_scan.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only failed scans can be resumed (current status: {failed_scan.status})",
        )

    now = datetime.now(UTC)
    latest_scan = await repo.get_latest_scan(project_id)
    if latest_scan is not None and latest_scan.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already running for this project.",
        )

    if not project.client_id or not project.encrypted_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project has no app credentials configured.",
        )

    crypto = CryptoService(settings)
    client_secret = crypto.decrypt(project.encrypted_client_secret)

    scan = ScanRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        target_tenant_id=project.target_tenant_id,
        scan_type=failed_scan.scan_type,
        auth_mode="app",
        status="running",
        resumed_from_scan_id=failed_scan.id,
        phases=[ScanPhase(name=p) for p in _DEFAULT_PHASES],
        started_at=now,
    )

    cosmos_database = project.database_name
    function_payload = {
        "tenant_id": project.target_tenant_id,
        "client_id": project.client_id,
        "client_secret": client_secret,
        "project_id": project_id,
        "scan_id": scan.id,
        "cosmos_endpoint": settings.cosmos_endpoint,
        "cosmos_key": settings.cosmos_key,
        "cosmos_database": cosmos_database,
        "graph_api_version": settings.graph_api_version,
        "resume_from_scan_id": failed_scan.id,
    }

    try:
        result = await _start_function_app_scan(settings, function_payload)
    except Exception as exc:
        logger.error("Failed to start resumed scan: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to start scan orchestration.",
        ) from exc

    scan.orchestration_instance_id = result.get("id")
    scan.orchestration_status_uri = result.get("statusQueryGetUri")
    await repo.upsert_scan(scan)

    broker: ScanEventBroker = request.app.state.scan_event_broker
    if broker is not None:
        await _publish_scan_event(
            broker,
            project_id,
            scan_id=scan.id,
            type="scan.resumed",
            message=f"Resuming {scan.scan_type} scan (original: {failed_scan.id[:8]}).",
            status="running",
        )

    if scan.orchestration_status_uri:
        task = asyncio.create_task(
            _poll_orchestration_status(
                request.app,
                repo,
                project_id,
                scan.id,
                scan.orchestration_status_uri,
                settings.scan_function_key,
            )
        )
        request.app.state.scan_tasks[scan.id] = task
        task.add_done_callback(lambda t, sid=scan.id: request.app.state.scan_tasks.pop(sid, None))

    return {
        "scan_id": scan.id,
        "status": "running",
        "auth_mode": "app",
        "resumed_from": failed_scan.id,
    }


@router.get("/{scan_id}/logs")
async def get_scan_logs(
    project_id: str,
    scan_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=100, ge=1, le=500),
    level: str | None = Query(default=None, pattern="^(info|warning|error)$"),
    phase: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get persisted scan log entries for a scan."""
    project_repo = await _get_project_repo(request, project_id, user, repo, settings)
    scan = await repo.get_scan(project_id, scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    offset = (page - 1) * size
    items, total = await project_repo.get_scan_logs(
        scan_id, offset=offset, limit=size, level=level, phase=phase
    )
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/events")
async def stream_scan_events(
    project_id: str,
    request: Request,
    scan_id: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
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
                except TimeoutError:
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
    repo: MasterRepo = Depends(get_master_repo),
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
    repo: MasterRepo = Depends(get_master_repo),
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
    repo: MasterRepo = Depends(get_master_repo),
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
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get scan detail with phase breakdown."""
    await validate_project_access(project_id, user, repo, settings)
    scan = await repo.get_scan(project_id, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan.model_dump(mode="json")
