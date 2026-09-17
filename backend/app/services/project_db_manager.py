# backend/app/services/project_db_manager.py
from __future__ import annotations

import logging

from azure.cosmos import PartitionKey
from azure.cosmos.aio import CosmosClient, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.services.cosmos_schema import PROJECT_CONTAINERS

logger = logging.getLogger(__name__)


class ProjectDatabaseManager:
    """Manages per-project Cosmos DB database lifecycle."""

    def __init__(self, client: CosmosClient) -> None:
        self._client = client

    async def provision_project_database(self, project_id: str) -> str:
        """Create a database and all project containers. Returns database name."""
        database_name = f"project-{project_id}"
        db = await self._client.create_database_if_not_exists(database_name)
        await self._ensure_containers(db)
        return database_name

    async def ensure_project_database(self, database_name: str) -> None:
        """Apply additive container schema changes to an existing project database."""
        db = self._client.get_database_client(database_name)
        await self._ensure_containers(db)

    async def _ensure_containers(self, db: DatabaseProxy) -> None:
        for container_def in PROJECT_CONTAINERS:
            kwargs: dict[str, object] = {
                "id": container_def.name,
                "partition_key": PartitionKey(path=container_def.partition_key_path),
            }
            if container_def.default_ttl is not None:
                kwargs["default_ttl"] = container_def.default_ttl
            if container_def.indexing_policy is not None:
                kwargs["indexing_policy"] = container_def.indexing_policy

            await db.create_container_if_not_exists(**kwargs)

        logger.info("Ensured project database containers (%d)", len(PROJECT_CONTAINERS))

    async def delete_project_database(self, database_name: str) -> None:
        """Delete an entire project database and all its data."""
        try:
            await self._client.delete_database(database_name)
            logger.info("Deleted project database %s", database_name)
        except CosmosResourceNotFoundError:
            logger.info("Database %s already deleted, skipping", database_name)
