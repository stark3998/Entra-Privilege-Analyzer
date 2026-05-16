"""Synchronous Cosmos DB writer for Azure Functions activities.

Uses module-level client caching and transactional batch upserts via
Cosmos DB's execute_item_batch API, with automatic fallback to individual
upserts when a batch fails.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from azure.cosmos import CosmosClient, PartitionKey

logger = logging.getLogger(__name__)

_BATCH_SIZE_LIMIT = 100

# Maps container name -> Python dict key used as the partition key value.
# Cosmos partition key paths are /<field>, but we need the dict key to
# extract the value from each item for grouping and batch calls.
_CONTAINER_PK_FIELD: dict[str, str] = {
    "identity_profiles": "id",
    "action_events": "identity_id",
    "role_recommendations": "identity_id",
    "drift_alerts": "identity_id",
    "baselines": "identity_id",
    "best_practice_violations": "id",
    "app_registrations": "id",
    "mfa_records": "id",
    "ca_policies": "id",
    "risk_detections": "id",
    "groups": "id",
    "scan_events": "scanId",
    "scan_staging": "scanId",
}

_client_cache: dict[str, CosmosClient] = {}
_container_cache: dict[str, Any] = {}


def _get_client(endpoint: str, key: str) -> CosmosClient:
    cache_key = f"{endpoint}:{key[:12]}"
    if cache_key not in _client_cache:
        _client_cache[cache_key] = CosmosClient(endpoint, credential=key)
    return _client_cache[cache_key]


def _get_container(
    endpoint: str,
    key: str,
    database: str,
    container_name: str,
    partition_key: str = "/tenantId",
):
    cache_key = f"{database}::{container_name}"
    if cache_key not in _container_cache:
        client = _get_client(endpoint, key)
        db = client.get_database_client(database)
        _container_cache[cache_key] = db.get_container_client(container_name)
    return _container_cache[cache_key]


def _get_pk_field(container_name: str) -> str:
    """Return the Python dict key for the partition key of a given container."""
    return _CONTAINER_PK_FIELD.get(container_name, "id")


def _batch_upsert(container: Any, items: list[dict], pk_field: str) -> int:
    """Upsert items using Cosmos DB transactional batch API.

    Groups items by partition key value, splits each group into chunks of
    up to 100 operations (the transactional batch limit), and executes
    each chunk as a single batch. Falls back to individual upserts if a
    batch call fails.

    Returns the total count of successfully written items.
    """
    if not items:
        return 0

    # Group items by their partition key value
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        pk_value = str(item.get(pk_field, item.get("id")))
        groups[pk_value].append(item)

    total_written = 0

    for pk_value, group_items in groups.items():
        # Split into chunks of _BATCH_SIZE_LIMIT
        for chunk_start in range(0, len(group_items), _BATCH_SIZE_LIMIT):
            chunk = group_items[chunk_start : chunk_start + _BATCH_SIZE_LIMIT]
            batch_operations = [("upsert", (doc,), {}) for doc in chunk]

            try:
                container.execute_item_batch(
                    batch_operations=batch_operations,
                    partition_key=pk_value,
                )
                total_written += len(chunk)
                logger.debug(
                    "Batch upsert succeeded: pk=%s, count=%d", pk_value, len(chunk),
                )
            except Exception as batch_exc:
                logger.warning(
                    "Batch upsert failed for pk=%s (%d items), falling back to "
                    "individual upserts: %s",
                    pk_value,
                    len(chunk),
                    batch_exc,
                )
                # Fallback: upsert items individually
                for doc in chunk:
                    try:
                        container.upsert_item(doc)
                        total_written += 1
                    except Exception as exc:
                        logger.error(
                            "Individual upsert failed for %s: %s",
                            doc.get("id", "?"),
                            exc,
                        )

    return total_written


def upsert_action_events(
    endpoint: str,
    key: str,
    database: str,
    tenant_id: str,
    events: list[dict[str, Any]],
) -> int:
    container = _get_container(endpoint, key, database, "action_events")
    pk_field = _get_pk_field("action_events")
    for e in events:
        e["tenantId"] = tenant_id
    return _batch_upsert(container, events, pk_field)


def upsert_identity_profile(
    endpoint: str,
    key: str,
    database: str,
    tenant_id: str,
    profile: dict[str, Any],
) -> None:
    container = _get_container(endpoint, key, database, "identity_profiles")
    profile["tenantId"] = tenant_id
    container.upsert_item(profile)


def write_scan_staging(
    endpoint: str,
    key: str,
    database: str,
    scan_id: str,
    data_type: str,
    items: list[dict[str, Any]],
    page: int = 0,
) -> int:
    container = _get_container(
        endpoint, key, database, "scan_staging", partition_key="/scanId",
    )
    doc = {
        "id": f"{scan_id}_{data_type}_{page}",
        "scanId": scan_id,
        "data_type": data_type,
        "page": page,
        "items": items,
        "count": len(items),
    }
    container.upsert_item(doc)
    return len(items)


def read_scan_staging(
    endpoint: str,
    key: str,
    database: str,
    scan_id: str,
    data_type: str,
) -> list[dict[str, Any]]:
    container = _get_container(
        endpoint, key, database, "scan_staging", partition_key="/scanId",
    )
    query = (
        "SELECT * FROM c WHERE c.scanId = @sid AND c.data_type = @dt "
        "ORDER BY c.page ASC"
    )
    params = [
        {"name": "@sid", "value": scan_id},
        {"name": "@dt", "value": data_type},
    ]
    pages = list(container.query_items(query=query, parameters=params, partition_key=scan_id))
    all_items: list[dict[str, Any]] = []
    for page_doc in pages:
        all_items.extend(page_doc.get("items", []))
    return all_items


def cleanup_scan_staging(
    endpoint: str,
    key: str,
    database: str,
    scan_id: str,
) -> int:
    container = _get_container(
        endpoint, key, database, "scan_staging", partition_key="/scanId",
    )
    query = "SELECT c.id FROM c WHERE c.scanId = @sid"
    params = [{"name": "@sid", "value": scan_id}]
    docs = list(container.query_items(query=query, parameters=params, partition_key=scan_id))
    deleted = 0
    for doc in docs:
        try:
            container.delete_item(item=doc["id"], partition_key=scan_id)
            deleted += 1
        except Exception as exc:
            logger.warning("Failed to delete staging doc %s: %s", doc["id"], exc)
    return deleted


def write_scan_event(
    endpoint: str,
    key: str,
    database: str,
    *,
    scan_id: str,
    project_id: str,
    event_type: str,
    message: str,
    level: str = "info",
    phase: str | None = None,
    status: str | None = None,
    items_processed: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Write a structured milestone event to the scan_events container.

    Never raises — logs a warning on failure so activity execution is unaffected.
    """
    try:
        container = _get_container(
            endpoint, key, database, "scan_events", partition_key="/scanId",
        )
        doc = {
            "id": f"{scan_id}:{event_type}:{uuid.uuid4().hex[:8]}",
            "scanId": scan_id,
            "scan_id": scan_id,
            "project_id": project_id,
            "type": event_type,
            "message": message,
            "level": level,
            "phase": phase,
            "status": status,
            "items_processed": items_processed,
            "timestamp": datetime.now(UTC).isoformat(),
            "details": details or {},
            "ttl": 7776000,
        }
        container.upsert_item(doc)
    except Exception as exc:
        logger.warning("Failed to write scan event %s for scan %s: %s", event_type, scan_id, exc)


def query_action_events_for_identity(
    endpoint: str,
    key: str,
    database: str,
    tenant_id: str,
    identity_id: str,
) -> list[dict[str, Any]]:
    container = _get_container(endpoint, key, database, "action_events")
    query = (
        "SELECT * FROM c WHERE c.tenantId = @tid AND c.identity_id = @iid"
    )
    params = [
        {"name": "@tid", "value": tenant_id},
        {"name": "@iid", "value": identity_id},
    ]
    return list(container.query_items(
        query=query, parameters=params, partition_key=tenant_id,
    ))
