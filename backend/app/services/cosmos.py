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
from app.models.best_practice import BestPracticeViolation
from app.models.drift import BaselineStats, DriftAlert
from app.models.identity import IdentityProfile
from app.models.narrative import Narrative
from app.models.role import RoleRecommendation
from app.models.tenant import TenantConfig

logger = logging.getLogger(__name__)

_repo: CosmosRepo | None = None

_ACTION_EVENTS_TTL = 7776000  # 90 days
_NARRATIVES_TTL = 86400  # 24 hours


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
        drift_alerts: ContainerProxy,
        baselines: ContainerProxy,
        best_practice_violations: ContainerProxy,
        narratives: ContainerProxy,
    ) -> None:
        self._client = client
        self._db = db
        self._tenant_configs = tenant_configs
        self._identity_profiles = identity_profiles
        self._action_events = action_events
        self._sync_state = sync_state
        self._role_recommendations = role_recommendations
        self._drift_alerts = drift_alerts
        self._baselines = baselines
        self._best_practice_violations = best_practice_violations
        self._narratives = narratives

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
        drift_alerts = await db.create_container_if_not_exists(
            id="drift_alerts",
            partition_key=PartitionKey(path="/tenantId"),
        )
        baselines = await db.create_container_if_not_exists(
            id="baselines",
            partition_key=PartitionKey(path="/tenantId"),
        )
        best_practice_violations = await db.create_container_if_not_exists(
            id="best_practice_violations",
            partition_key=PartitionKey(path="/tenantId"),
        )
        narratives = await db.create_container_if_not_exists(
            id="narratives",
            partition_key=PartitionKey(path="/tenantId"),
            default_ttl=_NARRATIVES_TTL,
        )

        logger.info(
            "Cosmos DB initialised — database=%s, containers="
            "tenant_configs,identity_profiles,action_events,sync_state,"
            "role_recommendations,drift_alerts,baselines,"
            "best_practice_violations,narratives",
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
            drift_alerts=drift_alerts,
            baselines=baselines,
            best_practice_violations=best_practice_violations,
            narratives=narratives,
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
    # Drift alert operations
    # ------------------------------------------------------------------

    async def get_drift_alert(self, tenant_id: str, alert_id: str) -> DriftAlert | None:
        """Point-read a drift alert by tenant and alert ID."""
        try:
            item: dict[str, Any] = await self._drift_alerts.read_item(
                item=alert_id,
                partition_key=tenant_id,
            )
            return DriftAlert.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_drift_alert(self, tenant_id: str, alert: DriftAlert) -> DriftAlert:
        """Insert or replace a drift alert."""
        body = alert.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._drift_alerts.upsert_item(body=body)
            return DriftAlert.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_drift_alert failed for %s/%s: %s",
                tenant_id,
                alert.id,
                exc.message,
            )
            raise

    async def list_drift_alerts(
        self,
        tenant_id: str,
        severity: str | None = None,
        drift_status: str | None = None,
        identity_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DriftAlert], int]:
        """List drift alerts for a tenant with optional filters.

        Returns (items, total_count). All queries are parameterized.
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, Any]] = [{"name": "@tenantId", "value": tenant_id}]

        if severity is not None:
            conditions.append("c.severity = @severity")
            parameters.append({"name": "@severity", "value": severity})

        if drift_status is not None:
            conditions.append("c.status = @driftStatus")
            parameters.append({"name": "@driftStatus", "value": drift_status})

        if identity_id is not None:
            conditions.append("c.identity_id = @identityId")
            parameters.append({"name": "@identityId", "value": identity_id})

        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._drift_alerts.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c.detected_at DESC OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[DriftAlert] = [
            DriftAlert.model_validate(item)
            async for item in self._drift_alerts.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Baseline operations
    # ------------------------------------------------------------------

    async def upsert_baseline(self, tenant_id: str, baseline: BaselineStats) -> BaselineStats:
        """Insert or replace a baseline stats document."""
        body = baseline.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._baselines.upsert_item(body=body)
            return BaselineStats.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_baseline failed for %s/%s: %s",
                tenant_id,
                baseline.id,
                exc.message,
            )
            raise

    async def list_baselines(
        self, tenant_id: str, identity_id: str,
    ) -> list[BaselineStats]:
        """List all baseline stats for a specific identity."""
        query = "SELECT * FROM c WHERE c.tenantId = @tenantId AND c.identity_id = @identityId"
        parameters: list[dict[str, str]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@identityId", "value": identity_id},
        ]
        items: list[BaselineStats] = [
            BaselineStats.model_validate(item)
            async for item in self._baselines.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        return items

    # ------------------------------------------------------------------
    # Best practice violation operations
    # ------------------------------------------------------------------

    async def get_violation(
        self, tenant_id: str, violation_id: str,
    ) -> BestPracticeViolation | None:
        """Point-read a best practice violation by tenant and violation ID."""
        try:
            item: dict[str, Any] = await self._best_practice_violations.read_item(
                item=violation_id,
                partition_key=tenant_id,
            )
            return BestPracticeViolation.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_violation(
        self, tenant_id: str, violation: BestPracticeViolation,
    ) -> BestPracticeViolation:
        """Insert or replace a best practice violation."""
        body = violation.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._best_practice_violations.upsert_item(
                body=body,
            )
            return BestPracticeViolation.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_violation failed for %s/%s: %s",
                tenant_id,
                violation.id,
                exc.message,
            )
            raise

    async def list_violations(
        self,
        tenant_id: str,
        violation_type: str | None = None,
        priority: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[BestPracticeViolation], int]:
        """List best practice violations for a tenant with optional filters.

        Returns (items, total_count). All queries are parameterized.
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, Any]] = [{"name": "@tenantId", "value": tenant_id}]

        if violation_type is not None:
            conditions.append("c.violation_type = @violationType")
            parameters.append({"name": "@violationType", "value": violation_type})

        if priority is not None:
            conditions.append("c.priority = @priority")
            parameters.append({"name": "@priority", "value": priority})

        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._best_practice_violations.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c.detected_at DESC OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[BestPracticeViolation] = [
            BestPracticeViolation.model_validate(item)
            async for item in self._best_practice_violations.query_items(
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

    async def list_sync_states_by_prefix(
        self, tenant_id: str, prefix: str,
    ) -> list[dict[str, Any]]:
        """Query sync_state documents whose sync_type starts with a prefix."""
        query = (
            "SELECT * FROM c WHERE c.tenantId = @tenantId "
            "AND STARTSWITH(c.sync_type, @prefix)"
        )
        parameters: list[dict[str, str]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@prefix", "value": prefix},
        ]
        return [
            item
            async for item in self._sync_state.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]

    # ------------------------------------------------------------------
    # Narrative operations
    # ------------------------------------------------------------------

    async def get_narrative(self, tenant_id: str, narrative_id: str) -> Narrative | None:
        """Point-read a narrative by tenant and narrative ID."""
        try:
            item: dict[str, Any] = await self._narratives.read_item(
                item=narrative_id,
                partition_key=tenant_id,
            )
            return Narrative.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_narrative(self, tenant_id: str, narrative: Narrative) -> Narrative:
        """Insert or replace a narrative document."""
        body = narrative.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._narratives.upsert_item(body=body)
            return Narrative.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_narrative failed for %s/%s: %s",
                tenant_id,
                narrative.id,
                exc.message,
            )
            raise

    # ------------------------------------------------------------------
    # Generic count query
    # ------------------------------------------------------------------

    async def count_items(self, tenant_id: str, container_name: str) -> int:
        """Count all items in a container for a given tenant."""
        container_map: dict[str, ContainerProxy] = {
            "tenant_configs": self._tenant_configs,
            "identity_profiles": self._identity_profiles,
            "action_events": self._action_events,
            "sync_state": self._sync_state,
            "role_recommendations": self._role_recommendations,
            "drift_alerts": self._drift_alerts,
            "baselines": self._baselines,
            "best_practice_violations": self._best_practice_violations,
            "narratives": self._narratives,
        }
        container = container_map.get(container_name)
        if container is None:
            return 0

        query = "SELECT VALUE COUNT(1) FROM c WHERE c.tenantId = @tenantId"
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        results: list[int] = [
            item
            async for item in container.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        return results[0] if results else 0

    # ------------------------------------------------------------------
    # Dashboard aggregation helpers
    # ------------------------------------------------------------------

    async def get_dashboard_summary(self, tenant_id: str) -> dict[str, Any]:
        """Run cross-container aggregation queries for the executive dashboard."""
        # Total identities
        total_identities = await self.count_items(tenant_id, "identity_profiles")

        # Total actions
        total_actions = await self.count_items(tenant_id, "action_events")

        # Identities by type
        type_query = (
            "SELECT c.identity_type, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId "
            "GROUP BY c.identity_type"
        )
        type_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        identities_by_type: dict[str, int] = {}
        async for item in self._identity_profiles.query_items(
            query=type_query, parameters=type_params, partition_key=tenant_id,
        ):
            identities_by_type[item.get("identity_type", "unknown")] = item.get("cnt", 0)

        # Avg risk score and high risk count
        risk_query = (
            "SELECT VALUE {"
            "  avg_risk: AVG(c.risk_score),"
            "  high_count: COUNT(c.risk_score > 70 ? 1 : undefined)"
            "} FROM c WHERE c.tenantId = @tenantId"
        )
        risk_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        risk_results: list[dict[str, Any]] = [
            item
            async for item in self._identity_profiles.query_items(
                query=risk_query, parameters=risk_params, partition_key=tenant_id,
            )
        ]
        avg_risk = 0.0
        high_risk_count = 0
        if risk_results:
            avg_risk = risk_results[0].get("avg_risk") or 0.0
            high_risk_count = risk_results[0].get("high_count") or 0

        # Open drift alerts
        drift_open_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.tenantId = @tenantId AND c.status = 'open'"
        )
        drift_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        drift_open_results: list[int] = [
            item
            async for item in self._drift_alerts.query_items(
                query=drift_open_query, parameters=drift_params, partition_key=tenant_id,
            )
        ]
        drift_alerts_open = drift_open_results[0] if drift_open_results else 0

        # Drift alerts by severity
        sev_query = (
            "SELECT c.severity, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.status = 'open' "
            "GROUP BY c.severity"
        )
        sev_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        drift_alerts_by_severity: dict[str, int] = {}
        async for item in self._drift_alerts.query_items(
            query=sev_query, parameters=sev_params, partition_key=tenant_id,
        ):
            drift_alerts_by_severity[item.get("severity", "unknown")] = item.get("cnt", 0)

        # Compliance score from best practice violations
        bp_total = await self.count_items(tenant_id, "best_practice_violations")
        bp_resolved_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.tenantId = @tenantId AND c.resolved = true"
        )
        bp_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        bp_resolved_results: list[int] = [
            item
            async for item in self._best_practice_violations.query_items(
                query=bp_resolved_query, parameters=bp_params, partition_key=tenant_id,
            )
        ]
        bp_resolved = bp_resolved_results[0] if bp_resolved_results else 0
        compliance_score = (bp_resolved / bp_total * 100.0) if bp_total > 0 else 100.0

        # Top 10 risky identities
        top_query = (
            "SELECT c.id, c.display_name, c.identity_type, c.risk_score "
            "FROM c WHERE c.tenantId = @tenantId "
            "ORDER BY c.risk_score DESC OFFSET 0 LIMIT 10"
        )
        top_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        top_risky: list[dict[str, Any]] = [
            item
            async for item in self._identity_profiles.query_items(
                query=top_query, parameters=top_params, partition_key=tenant_id,
            )
        ]

        # Recommendations count and avg reduction
        rec_query = (
            "SELECT VALUE {"
            "  cnt: COUNT(1),"
            "  avg_reduction: AVG(c.reduction_score)"
            "} FROM c WHERE c.tenantId = @tenantId"
        )
        rec_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        rec_results: list[dict[str, Any]] = [
            item
            async for item in self._role_recommendations.query_items(
                query=rec_query, parameters=rec_params, partition_key=tenant_id,
            )
        ]
        recommendations_count = 0
        avg_reduction_score = 0.0
        if rec_results:
            recommendations_count = rec_results[0].get("cnt") or 0
            avg_reduction_score = rec_results[0].get("avg_reduction") or 0.0

        return {
            "total_identities": total_identities,
            "total_actions": total_actions,
            "identities_by_type": identities_by_type,
            "avg_risk_score": avg_risk,
            "high_risk_count": high_risk_count,
            "drift_alerts_open": drift_alerts_open,
            "drift_alerts_by_severity": drift_alerts_by_severity,
            "compliance_score": compliance_score,
            "top_risky_identities": top_risky,
            "recommendations_count": recommendations_count,
            "avg_reduction_score": avg_reduction_score,
        }

    async def get_trends(self, tenant_id: str, days: int = 30) -> dict[str, Any]:
        """Compute daily trend data for the dashboard over the last N days."""
        from datetime import UTC, datetime, timedelta

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        # Daily action counts
        actions_query = (
            "SELECT SUBSTRING(c.timestamp, 0, 10) AS date, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "GROUP BY SUBSTRING(c.timestamp, 0, 10)"
        )
        actions_params: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@cutoff", "value": cutoff},
        ]
        actions_trend: list[dict[str, Any]] = []
        async for item in self._action_events.query_items(
            query=actions_query, parameters=actions_params, partition_key=tenant_id,
        ):
            actions_trend.append({
                "date": item.get("date", ""),
                "value": float(item.get("cnt", 0)),
            })

        # Daily drift alert counts
        drift_query = (
            "SELECT SUBSTRING(c.detected_at, 0, 10) AS date, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.detected_at >= @cutoff "
            "GROUP BY SUBSTRING(c.detected_at, 0, 10)"
        )
        drift_params: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@cutoff", "value": cutoff},
        ]
        drift_alerts_trend: list[dict[str, Any]] = []
        async for item in self._drift_alerts.query_items(
            query=drift_query, parameters=drift_params, partition_key=tenant_id,
        ):
            drift_alerts_trend.append({
                "date": item.get("date", ""),
                "value": float(item.get("cnt", 0)),
            })

        # Risk score trend — use an empty placeholder since risk is a snapshot, not time-series
        risk_score_trend: list[dict[str, Any]] = []

        return {
            "risk_score_trend": risk_score_trend,
            "drift_alerts_trend": drift_alerts_trend,
            "actions_trend": actions_trend,
        }

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
