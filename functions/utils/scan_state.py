"""Read and update ScanRecord / ScanPhase documents in Cosmos DB.

The function app writes to the same scan_history container as the backend
so progress is visible to the frontend via the existing poll endpoint.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from azure.cosmos import CosmosClient

logger = logging.getLogger(__name__)

_client_cache: dict[str, CosmosClient] = {}


def _get_client(endpoint: str, key: str) -> CosmosClient:
    cache_key = f"{endpoint}:{key[:12]}"
    if cache_key not in _client_cache:
        _client_cache[cache_key] = CosmosClient(endpoint, credential=key)
    return _client_cache[cache_key]


def _get_scan_container(endpoint: str, key: str, database: str):
    client = _get_client(endpoint, key)
    db = client.get_database_client(database)
    return db.get_container_client("scan_history")


def _get_project_container(endpoint: str, key: str, database: str):
    client = _get_client(endpoint, key)
    db = client.get_database_client(database)
    return db.get_container_client("projects")


def get_scan_record(
    endpoint: str, key: str, database: str,
    project_id: str, scan_id: str,
) -> dict[str, Any] | None:
    container = _get_scan_container(endpoint, key, database)
    try:
        return container.read_item(item=scan_id, partition_key=project_id)
    except Exception:
        return None


def update_scan_phase(
    endpoint: str,
    key: str,
    database: str,
    project_id: str,
    scan_id: str,
    phase_name: str,
    status: str,
    items_processed: int = 0,
    checkpoint_next_link: str | None = None,
) -> None:
    container = _get_scan_container(endpoint, key, database)
    scan = container.read_item(item=scan_id, partition_key=project_id)

    now = datetime.now(UTC).isoformat()
    for phase in scan.get("phases", []):
        if phase["name"] == phase_name:
            phase["status"] = status
            if status == "running" and phase.get("started_at") is None:
                phase["started_at"] = now
            if status in ("completed", "failed", "skipped"):
                phase["completed_at"] = now
            phase["items_processed"] = items_processed
            if checkpoint_next_link is not None:
                phase["checkpoint_next_link"] = checkpoint_next_link
            break

    container.upsert_item(scan)


def get_previous_scan_phases(
    endpoint: str,
    key: str,
    database: str,
    project_id: str,
    scan_id: str,
) -> list[dict[str, Any]]:
    scan = get_scan_record(endpoint, key, database, project_id, scan_id)
    if scan is None:
        return []
    return scan.get("phases", [])


def finalize_scan(
    endpoint: str,
    key: str,
    database: str,
    project_id: str,
    scan_id: str,
    status: str,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    container = _get_scan_container(endpoint, key, database)
    scan = container.read_item(item=scan_id, partition_key=project_id)

    now = datetime.now(UTC).isoformat()
    scan["status"] = status
    scan["completed_at"] = now
    scan["owner_instance_id"] = None
    scan["heartbeat_at"] = None
    scan["lease_expires_at"] = None

    if error_message:
        scan["error_message"] = error_message

    if status == "failed":
        for phase in scan.get("phases", []):
            if phase["status"] in ("pending", "running"):
                phase["status"] = "failed"
                phase["completed_at"] = now

    container.upsert_item(scan)

    proj_container = _get_project_container(endpoint, key, database)
    try:
        project = proj_container.read_item(item=project_id, partition_key=project_id)
        project["last_scan_at"] = now
        project["last_scan_status"] = status
        if summary and status == "completed":
            project["identity_count"] = summary.get("identities_processed", 0)
        project["updated_at"] = now
        proj_container.upsert_item(project)
    except Exception as exc:
        logger.warning("Failed to update project %s after scan: %s", project_id, exc)


def upsert_sync_state(
    endpoint: str,
    key: str,
    database: str,
    tenant_id: str,
    sync_type: str,
    state: dict[str, Any],
) -> None:
    client = _get_client(endpoint, key)
    db = client.get_database_client(database)
    container = db.get_container_client("sync_state")
    doc = {
        "id": f"{tenant_id}_{sync_type}",
        "tenantId": tenant_id,
        "sync_type": sync_type,
        **state,
    }
    container.upsert_item(doc)
