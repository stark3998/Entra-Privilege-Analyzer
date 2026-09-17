from __future__ import annotations

import logging
import re

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient, DatabaseProxy

from app.services.cosmos_schema import TENANT_EVIDENCE_CONTAINERS

logger = logging.getLogger(__name__)

_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


def tenant_evidence_database_name(tenant_id: str) -> str:
    normalized = tenant_id.strip().lower()
    if not _TENANT_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Tenant ID must contain only letters, numbers, and hyphens")
    return f"tenant-{normalized}"


class TenantEvidenceDatabaseManager:
    def __init__(self, client: CosmosClient, raw_activity_ttl: int = 31536000) -> None:
        if raw_activity_ttl <= 0:
            raise ValueError("Raw activity TTL must be greater than zero")
        self._client = client
        self._raw_activity_ttl = raw_activity_ttl

    async def provision_tenant_database(self, tenant_id: str) -> str:
        database_name = tenant_evidence_database_name(tenant_id)
        db = await self._client.create_database_if_not_exists(database_name)
        await self._ensure_containers(db)
        return database_name

    async def ensure_tenant_database(self, tenant_id: str) -> None:
        db = await self._client.create_database_if_not_exists(
            tenant_evidence_database_name(tenant_id)
        )
        await self._ensure_containers(db)

    async def _ensure_containers(self, db: DatabaseProxy) -> None:
        for container_def in TENANT_EVIDENCE_CONTAINERS:
            kwargs: dict[str, object] = {
                "id": container_def.name,
                "partition_key": PartitionKey(path=container_def.partition_key_path),
            }
            ttl = container_def.default_ttl
            if container_def.name == "activity_events":
                ttl = self._raw_activity_ttl
            if ttl is not None:
                kwargs["default_ttl"] = ttl
            if container_def.indexing_policy is not None:
                kwargs["indexing_policy"] = container_def.indexing_policy
            await db.create_container_if_not_exists(**kwargs)
        logger.info(
            "Ensured tenant evidence database containers (%d)",
            len(TENANT_EVIDENCE_CONTAINERS),
        )
