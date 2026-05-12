# backend/app/services/cosmos.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from azure.cosmos import PartitionKey
from azure.cosmos.aio import ContainerProxy, CosmosClient, DatabaseProxy
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from app.config import Settings
from app.models.action import ActionEvent
from app.models.identity import IdentityProfile
from app.models.role import RoleRecommendation
from app.models.tenant import TenantConfig

logger = logging.getLogger(__name__)

_repo: CosmosRepo | None = None

_ACTION_EVENTS_TTL = 7776000  # 90 days


class CosmosRepo:
    """Repository for Cosmos DB operations, enforcing tenant isolation."""

    def __init__(
        self,
        client: CosmosClient,
        db: DatabaseProxy,
        tenant_configs: ContainerProxy,
        identity_profiles: ContainerProxy,
        action_events: ContainerProxy,
        sync_state: ContainerProxy,
        role_recommendations: ContainerProxy,
    ) -> None:
        self._client = client
        self._db = db
        self._tenant_configs = tenant_configs
        self._identity_profiles = identity_profiles
        self._action_events = action_events
        self._sync_state = sync_state
        self._role_recommendations = role_recommendations

    @classmethod
    async def create(cls, settings: Settings) -> CosmosRepo:
        """Factory that initialises the Cosmos client and ensures resources exist.

        Creates the database and all required containers if they do not already exist.
        """
        client = CosmosClient(url=settings.cosmos_endpoint, credential=settings.cosmos_key)

        db: DatabaseProxy = await client.create_database_if_not_exists(id=settings.cosmos_database)

        tenant_configs = await db.create_container_if_not_exists(
            id="tenant_configs",
            partition_key=PartitionKey(path="/tenantId"),
        )
        identity_profiles = await db.create_container_if_not_exists(
            id="identity_profiles",
            partition_key=PartitionKey(path="/tenantId"),
        )
        action_events = await db.create_container_if_not_exists(
            id="action_events",
            partition_key=PartitionKey(path="/tenantId"),
            default_ttl=_ACTION_EVENTS_TTL,
        )
        sync_state = await db.create_container_if_not_exists(
            id="sync_state",
            partition_key=PartitionKey(path="/tenantId"),
        )
        role_recommendations = await db.create_container_if_not_exists(
            id="role_recommendations",
            partition_key=PartitionKey(path="/tenantId"),
        )

        logger.info(
            "Cosmos DB initialised — database=%s, containers="
            "tenant_configs,identity_profiles,action_events,sync_state,role_recommendations",
            settings.cosmos_database,
        )
        return cls(
            client=client,
            db=db,
            tenant_configs=tenant_configs,
            identity_profiles=identity_profiles,
            action_events=action_events,
            sync_state=sync_state,
            role_recommendations=role_recommendations,
        )

    # ------------------------------------------------------------------
    # Tenant config operations
    # ------------------------------------------------------------------

    async def get_tenant_config(self, tenant_id: str) -> TenantConfig | None:
        """Point-read a tenant configuration by tenant_id.

        Returns None when the document does not exist.
        """
        try:
            item: dict[str, Any] = await self._tenant_configs.read_item(
                item=tenant_id,
                partition_key=tenant_id,
            )
            return TenantConfig.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_tenant_config(self, config: TenantConfig) -> TenantConfig:
        """Insert or replace a tenant configuration."""
        body = config.model_dump(mode="json")
        body["tenantId"] = config.tenant_id
        try:
            result: dict[str, Any] = await self._tenant_configs.upsert_item(body=body)
            return TenantConfig.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("Cosmos upsert failed for tenant %s: %s", config.tenant_id, exc.message)
            raise

    # ------------------------------------------------------------------
    # Identity profile operations
    # ------------------------------------------------------------------

    async def get_identity(self, tenant_id: str, identity_id: str) -> IdentityProfile | None:
        """Point-read an identity profile by tenant and identity ID."""
        try:
            item: dict[str, Any] = await self._identity_profiles.read_item(
                item=identity_id,
                partition_key=tenant_id,
            )
            return IdentityProfile.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_identity(
        self, tenant_id: str, profile: IdentityProfile
    ) -> IdentityProfile:
        """Insert or replace an identity profile."""
        body = profile.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._identity_profiles.upsert_item(body=body)
            return IdentityProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_identity failed for %s/%s: %s",
                tenant_id,
                profile.id,
                exc.message,
            )
            raise

    async def list_identities(
        self,
        tenant_id: str,
        identity_type: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[IdentityProfile], int]:
        """List identity profiles for a tenant with optional filters.

        Returns (items, total_count). All queries are parameterized.
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]

        if identity_type is not None:
            conditions.append("c.identity_type = @identityType")
            parameters.append({"name": "@identityType", "value": identity_type})

        if search is not None:
            conditions.append(
                "(CONTAINS(LOWER(c.display_name), LOWER(@search))"
                " OR CONTAINS(LOWER(c.upn), LOWER(@search)))"
            )
            parameters.append({"name": "@search", "value": search})

        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._identity_profiles.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c.display_name OFFSET @offset LIMIT @limit"
        )
        data_params = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[IdentityProfile] = [
            IdentityProfile.model_validate(item)
            async for item in self._identity_profiles.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Action event operations
    # ------------------------------------------------------------------

    async def append_action_events(self, tenant_id: str, events: list[ActionEvent]) -> int:
        """Bulk-insert action events. Returns count of items inserted.

        Uses upsert so re-runs with the same deterministic IDs are idempotent.
        """
        inserted = 0
        for event in events:
            body = event.model_dump(mode="json")
            body["tenantId"] = tenant_id
            try:
                await self._action_events.upsert_item(body=body)
                inserted += 1
            except CosmosHttpResponseError as exc:
                logger.warning(
                    "Failed to insert action event %s: %s", event.id, exc.message
                )
        return inserted

    async def list_actions(
        self,
        tenant_id: str,
        identity_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ActionEvent], int]:
        """List action events for a specific identity within an optional time range.

        Returns (items, total_count). All queries are parameterized.
        """
        conditions = [
            "c.tenantId = @tenantId",
            "c.identity_id = @identityId",
        ]
        parameters: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@identityId", "value": identity_id},
        ]

        if start is not None:
            conditions.append("c.timestamp >= @start")
            parameters.append({"name": "@start", "value": start.isoformat()})

        if end is not None:
            conditions.append("c.timestamp <= @end")
            parameters.append({"name": "@end", "value": end.isoformat()})

        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._action_events.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c.timestamp DESC OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[ActionEvent] = [
            ActionEvent.model_validate(item)
            async for item in self._action_events.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Role recommendation operations
    # ------------------------------------------------------------------

    async def get_recommendation(
        self, tenant_id: str, identity_id: str,
    ) -> RoleRecommendation | None:
        """Point-read a role recommendation by tenant and identity ID."""
        try:
            item: dict[str, Any] = await self._role_recommendations.read_item(
                item=identity_id,
                partition_key=tenant_id,
            )
            return RoleRecommendation.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_recommendation(
        self, tenant_id: str, rec: RoleRecommendation,
    ) -> RoleRecommendation:
        """Insert or replace a role recommendation."""
        body = rec.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._role_recommendations.upsert_item(body=body)
            return RoleRecommendation.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_recommendation failed for %s/%s: %s",
                tenant_id,
                rec.identity_id,
                exc.message,
            )
            raise

    async def list_recommendations(
        self,
        tenant_id: str,
        identity_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RoleRecommendation], int]:
        """List role recommendations for a tenant with optional identity_type filter.

        Returns (items, total_count). All queries are parameterized.
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, Any]] = [{"name": "@tenantId", "value": tenant_id}]

        if identity_type is not None:
            conditions.append("c.identity_type = @identityType")
            parameters.append({"name": "@identityType", "value": identity_type})

        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._role_recommendations.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c.reduction_score DESC OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[RoleRecommendation] = [
            RoleRecommendation.model_validate(item)
            async for item in self._role_recommendations.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Sync state operations
    # ------------------------------------------------------------------

    async def get_sync_state(self, tenant_id: str, sync_type: str) -> dict[str, Any] | None:
        """Read the sync state document for a given tenant and sync type."""
        doc_id = f"{tenant_id}_{sync_type}"
        try:
            item: dict[str, Any] = await self._sync_state.read_item(
                item=doc_id,
                partition_key=tenant_id,
            )
            return item
        except CosmosResourceNotFoundError:
            return None

    async def upsert_sync_state(
        self, tenant_id: str, sync_type: str, state: dict[str, Any]
    ) -> None:
        """Insert or replace a sync state document."""
        body = {
            "id": f"{tenant_id}_{sync_type}",
            "tenantId": tenant_id,
            "sync_type": sync_type,
            **state,
        }
        try:
            await self._sync_state.upsert_item(body=body)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_sync_state failed for %s/%s: %s",
                tenant_id,
                sync_type,
                exc.message,
            )
            raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying Cosmos client."""
        await self._client.close()


async def init_cosmos_repo(settings: Settings) -> CosmosRepo:
    """Create and cache the global CosmosRepo singleton."""
    global _repo
    _repo = await CosmosRepo.create(settings)
    return _repo


def get_cosmos_repo() -> CosmosRepo:
    """Return the global CosmosRepo instance.

    Raises RuntimeError if called before init_cosmos_repo().
    """
    if _repo is None:
        raise RuntimeError("CosmosRepo has not been initialised — call init_cosmos_repo() first")
    return _repo
