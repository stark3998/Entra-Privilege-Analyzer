"""Synchronous Cosmos DB writer for Azure Functions activities.

Uses module-level client caching and concurrent upserts via ThreadPoolExecutor,
following the pattern from Entra-Migration-Functions/utils/cosmos.py.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any

from azure.cosmos import CosmosClient, PartitionKey

logger = logging.getLogger(__name__)

_MAX_CONCURRENT_WRITES = 25

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


def _concurrent_upsert(container: Any, items: list[dict]) -> int:
    if not items:
        return 0
    count = 0

    def _upsert_one(item: dict) -> None:
        container.upsert_item(item)

    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_CONCURRENT_WRITES) as pool:
        futures = {pool.submit(_upsert_one, item): item for item in items}
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
                count += 1
            except Exception as exc:
                item = futures[future]
                logger.error("Cosmos upsert failed for %s: %s", item.get("id", "?"), exc)
    return count


def upsert_action_events(
    endpoint: str,
    key: str,
    database: str,
    tenant_id: str,
    events: list[dict[str, Any]],
) -> int:
    container = _get_container(endpoint, key, database, "action_events")
    for e in events:
        e["tenantId"] = tenant_id
    return _concurrent_upsert(container, events)


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
