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
from app.models.alert_rules import AlertRule, ScanSchedule
from app.models.best_practice import BestPracticeViolation
from app.models.drift import BaselineStats, DriftAlert
from app.models.identity import IdentityProfile
from app.models.narrative import Narrative
from app.models.project import Project, ProjectMember, ScanRecord
from app.models.role import RoleRecommendation
from app.models.access_review import AccessReviewDefinition
from app.models.app_registration import AppRegistrationProfile
from app.models.conditional_access import ConditionalAccessPolicyRecord
from app.models.custom_role import CustomRoleProfile
from app.models.group import GroupProfile
from app.models.mfa_status import MfaRegistrationRecord
from app.models.remediation import RemediationAction
from app.models.sod_policy import SodConflictRule
from app.models.pim_session import PimSession, PimSessionAnalytics
from app.models.access_path import AccessPathAnalysis, AccessPathSummary
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
        projects: ContainerProxy,
        project_members: ContainerProxy,
        scan_history: ContainerProxy,
        scan_schedules: ContainerProxy,
        alert_rules: ContainerProxy,
        app_registrations: ContainerProxy,
        mfa_records: ContainerProxy,
        ca_policies: ContainerProxy,
        risk_detections: ContainerProxy,
        groups: ContainerProxy,
        access_reviews: ContainerProxy,
        sod_rules: ContainerProxy,
        custom_roles: ContainerProxy,
        remediation_actions: ContainerProxy,
        pim_sessions: ContainerProxy,
        access_path_analyses: ContainerProxy,
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
        self._projects = projects
        self._project_members = project_members
        self._scan_history = scan_history
        self._scan_schedules = scan_schedules
        self._alert_rules = alert_rules
        self._app_registrations = app_registrations
        self._mfa_records = mfa_records
        self._ca_policies = ca_policies
        self._risk_detections = risk_detections
        self._groups = groups
        self._access_reviews = access_reviews
        self._sod_rules = sod_rules
        self._custom_roles = custom_roles
        self._remediation_actions = remediation_actions
        self._pim_sessions = pim_sessions
        self._access_path_analyses = access_path_analyses

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
        projects = await db.create_container_if_not_exists(
            id="projects",
            partition_key=PartitionKey(path="/ownerId"),
        )
        project_members = await db.create_container_if_not_exists(
            id="project_members",
            partition_key=PartitionKey(path="/projectId"),
        )
        scan_history = await db.create_container_if_not_exists(
            id="scan_history",
            partition_key=PartitionKey(path="/projectId"),
        )
        scan_schedules = await db.create_container_if_not_exists(
            id="scan_schedules",
            partition_key=PartitionKey(path="/projectId"),
        )
        alert_rules = await db.create_container_if_not_exists(
            id="alert_rules",
            partition_key=PartitionKey(path="/projectId"),
        )
        app_registrations = await db.create_container_if_not_exists(
            id="app_registrations",
            partition_key=PartitionKey(path="/tenantId"),
        )
        mfa_records = await db.create_container_if_not_exists(
            id="mfa_records",
            partition_key=PartitionKey(path="/tenantId"),
        )
        ca_policies = await db.create_container_if_not_exists(
            id="ca_policies",
            partition_key=PartitionKey(path="/tenantId"),
        )
        risk_detections = await db.create_container_if_not_exists(
            id="risk_detections",
            partition_key=PartitionKey(path="/tenantId"),
        )
        groups = await db.create_container_if_not_exists(
            id="groups",
            partition_key=PartitionKey(path="/tenantId"),
        )
        access_reviews = await db.create_container_if_not_exists(
            id="access_reviews",
            partition_key=PartitionKey(path="/tenantId"),
        )
        sod_rules = await db.create_container_if_not_exists(
            id="sod_rules",
            partition_key=PartitionKey(path="/tenantId"),
        )
        custom_roles = await db.create_container_if_not_exists(
            id="custom_roles",
            partition_key=PartitionKey(path="/tenantId"),
        )
        remediation_actions = await db.create_container_if_not_exists(
            id="remediation_actions",
            partition_key=PartitionKey(path="/tenantId"),
        )
        pim_sessions = await db.create_container_if_not_exists(
            id="pim_sessions",
            partition_key=PartitionKey(path="/tenantId"),
        )
        access_path_analyses = await db.create_container_if_not_exists(
            id="access_path_analyses",
            partition_key=PartitionKey(path="/tenantId"),
        )

        logger.info(
            "Cosmos DB initialised — database=%s, containers="
            "tenant_configs,identity_profiles,action_events,sync_state,"
            "role_recommendations,drift_alerts,baselines,"
            "best_practice_violations,narratives,projects,"
            "project_members,scan_history,scan_schedules,alert_rules,"
            "app_registrations,mfa_records,ca_policies,risk_detections,"
            "groups,access_reviews,sod_rules,custom_roles,remediation_actions,"
            "pim_sessions,access_path_analyses",
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
            projects=projects,
            project_members=project_members,
            scan_history=scan_history,
            scan_schedules=scan_schedules,
            alert_rules=alert_rules,
            app_registrations=app_registrations,
            mfa_records=mfa_records,
            ca_policies=ca_policies,
            risk_detections=risk_detections,
            groups=groups,
            access_reviews=access_reviews,
            sod_rules=sod_rules,
            custom_roles=custom_roles,
            remediation_actions=remediation_actions,
            pim_sessions=pim_sessions,
            access_path_analyses=access_path_analyses,
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
    # Project operations
    # ------------------------------------------------------------------

    async def get_project(self, project_id: str) -> Project | None:
        """Read a project by ID. Requires a cross-partition point-read."""
        query = "SELECT * FROM c WHERE c.id = @id"
        params: list[dict[str, str]] = [{"name": "@id", "value": project_id}]
        items: list[Project] = [
            Project.model_validate(item)
            async for item in self._projects.query_items(
                query=query, parameters=params,
            )
        ]
        return items[0] if items else None

    async def upsert_project(self, project: Project) -> Project:
        """Insert or replace a project document."""
        body = project.model_dump(mode="json")
        body["ownerId"] = project.owner_id
        try:
            result: dict[str, Any] = await self._projects.upsert_item(body=body)
            return Project.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("Cosmos upsert_project failed for %s: %s", project.id, exc.message)
            raise

    async def list_projects_for_user(
        self, user_id: str, email: str = "",
    ) -> list[Project]:
        """List all projects owned by a user plus projects they are a member of."""
        owned_query = "SELECT * FROM c WHERE c.ownerId = @userId"
        owned_params: list[dict[str, str]] = [{"name": "@userId", "value": user_id}]
        owned: list[Project] = [
            Project.model_validate(item)
            async for item in self._projects.query_items(
                query=owned_query, parameters=owned_params, partition_key=user_id,
            )
        ]

        memberships = await self.list_user_memberships(user_id, email)
        member_project_ids = {m.project_id for m in memberships} - {p.id for p in owned}

        for pid in member_project_ids:
            proj = await self.get_project(pid)
            if proj is not None:
                owned.append(proj)

        return owned

    async def delete_project(self, owner_id: str, project_id: str) -> None:
        """Delete a project and all its members and scan history."""
        try:
            await self._projects.delete_item(item=project_id, partition_key=owner_id)
        except CosmosResourceNotFoundError:
            pass

        members = await self.list_project_members(project_id)
        for m in members:
            try:
                await self._project_members.delete_item(item=m.id, partition_key=project_id)
            except CosmosResourceNotFoundError:
                pass

    # ------------------------------------------------------------------
    # Project member operations
    # ------------------------------------------------------------------

    async def get_project_member(
        self, project_id: str, user_id: str,
    ) -> ProjectMember | None:
        """Find a member record by project and user ID."""
        query = (
            "SELECT * FROM c WHERE c.projectId = @projectId "
            "AND c.user_id = @userId"
        )
        params: list[dict[str, str]] = [
            {"name": "@projectId", "value": project_id},
            {"name": "@userId", "value": user_id},
        ]
        items: list[ProjectMember] = [
            ProjectMember.model_validate(item)
            async for item in self._project_members.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]
        return items[0] if items else None

    async def get_project_member_by_email(
        self, project_id: str, email: str,
    ) -> ProjectMember | None:
        """Find a member record by project and email (case-insensitive)."""
        query = (
            "SELECT * FROM c WHERE c.projectId = @projectId "
            "AND LOWER(c.email) = LOWER(@email)"
        )
        params: list[dict[str, str]] = [
            {"name": "@projectId", "value": project_id},
            {"name": "@email", "value": email},
        ]
        items: list[ProjectMember] = [
            ProjectMember.model_validate(item)
            async for item in self._project_members.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]
        return items[0] if items else None

    async def upsert_project_member(self, member: ProjectMember) -> ProjectMember:
        """Insert or replace a project member document."""
        body = member.model_dump(mode="json")
        body["projectId"] = member.project_id
        try:
            result: dict[str, Any] = await self._project_members.upsert_item(body=body)
            return ProjectMember.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_project_member failed for %s/%s: %s",
                member.project_id, member.id, exc.message,
            )
            raise

    async def list_project_members(self, project_id: str) -> list[ProjectMember]:
        """List all members of a project."""
        query = "SELECT * FROM c WHERE c.projectId = @projectId"
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        return [
            ProjectMember.model_validate(item)
            async for item in self._project_members.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]

    async def delete_project_member(self, project_id: str, member_id: str) -> None:
        """Delete a project member."""
        try:
            await self._project_members.delete_item(item=member_id, partition_key=project_id)
        except CosmosResourceNotFoundError:
            pass

    async def list_user_memberships(
        self, user_id: str, email: str = "",
    ) -> list[ProjectMember]:
        """Find all project memberships for a user (cross-partition).

        Matches on user_id (OID) OR email to include unclaimed invites.
        """
        if email:
            query = (
                "SELECT * FROM c WHERE c.user_id = @userId "
                "OR LOWER(c.email) = LOWER(@email)"
            )
            params: list[dict[str, str]] = [
                {"name": "@userId", "value": user_id},
                {"name": "@email", "value": email},
            ]
        else:
            query = "SELECT * FROM c WHERE c.user_id = @userId"
            params = [{"name": "@userId", "value": user_id}]
        return [
            ProjectMember.model_validate(item)
            async for item in self._project_members.query_items(
                query=query, parameters=params,
            )
        ]

    # ------------------------------------------------------------------
    # Scan history operations
    # ------------------------------------------------------------------

    async def get_scan(self, project_id: str, scan_id: str) -> ScanRecord | None:
        """Point-read a scan record."""
        try:
            item: dict[str, Any] = await self._scan_history.read_item(
                item=scan_id, partition_key=project_id,
            )
            return ScanRecord.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_scan(self, scan: ScanRecord) -> ScanRecord:
        """Insert or replace a scan record."""
        body = scan.model_dump(mode="json")
        body["projectId"] = scan.project_id
        try:
            result: dict[str, Any] = await self._scan_history.upsert_item(body=body)
            return ScanRecord.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("Cosmos upsert_scan failed for %s/%s: %s", scan.project_id, scan.id, exc.message)
            raise

    async def list_scans(
        self, project_id: str, offset: int = 0, limit: int = 20,
    ) -> tuple[list[ScanRecord], int]:
        """List scan history for a project, newest first."""
        count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.projectId = @projectId"
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        count_results: list[int] = [
            item
            async for item in self._scan_history.query_items(
                query=count_query, parameters=params, partition_key=project_id,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            "SELECT * FROM c WHERE c.projectId = @projectId "
            "ORDER BY c.started_at DESC OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *params,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[ScanRecord] = [
            ScanRecord.model_validate(item)
            async for item in self._scan_history.query_items(
                query=data_query, parameters=data_params, partition_key=project_id,
            )
        ]
        return items, total

    async def get_latest_scan(self, project_id: str) -> ScanRecord | None:
        """Get the most recent scan for a project."""
        query = (
            "SELECT * FROM c WHERE c.projectId = @projectId "
            "ORDER BY c.started_at DESC OFFSET 0 LIMIT 1"
        )
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        items: list[ScanRecord] = [
            ScanRecord.model_validate(item)
            async for item in self._scan_history.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]
        return items[0] if items else None

    # ------------------------------------------------------------------
    # Scan schedule operations
    # ------------------------------------------------------------------

    async def get_scan_schedules(self) -> list[ScanSchedule]:
        """Return all enabled scan schedules (cross-partition)."""
        query = "SELECT * FROM c WHERE c.enabled = true"
        return [
            ScanSchedule.model_validate(item)
            async for item in self._scan_schedules.query_items(
                query=query, parameters=[],
            )
        ]

    async def get_scan_schedules_for_project(
        self, project_id: str,
    ) -> list[ScanSchedule]:
        """List all scan schedules for a project."""
        query = "SELECT * FROM c WHERE c.projectId = @projectId"
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        return [
            ScanSchedule.model_validate(item)
            async for item in self._scan_schedules.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]

    async def upsert_scan_schedule(self, schedule: ScanSchedule) -> ScanSchedule:
        """Insert or replace a scan schedule document."""
        body = schedule.model_dump(mode="json")
        body["projectId"] = schedule.project_id
        try:
            result: dict[str, Any] = await self._scan_schedules.upsert_item(body=body)
            return ScanSchedule.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_scan_schedule failed for %s/%s: %s",
                schedule.project_id, schedule.id, exc.message,
            )
            raise

    async def delete_scan_schedule(self, project_id: str, schedule_id: str) -> None:
        """Delete a scan schedule."""
        try:
            await self._scan_schedules.delete_item(
                item=schedule_id, partition_key=project_id,
            )
        except CosmosResourceNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Alert rule operations
    # ------------------------------------------------------------------

    async def get_alert_rules_for_project(
        self, project_id: str,
    ) -> list[AlertRule]:
        """List all alert rules for a project."""
        query = "SELECT * FROM c WHERE c.projectId = @projectId"
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        return [
            AlertRule.model_validate(item)
            async for item in self._alert_rules.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]

    async def get_alert_rule(
        self, project_id: str, rule_id: str,
    ) -> AlertRule | None:
        """Point-read an alert rule."""
        try:
            item: dict[str, Any] = await self._alert_rules.read_item(
                item=rule_id, partition_key=project_id,
            )
            return AlertRule.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_alert_rule(self, rule: AlertRule) -> AlertRule:
        """Insert or replace an alert rule document."""
        body = rule.model_dump(mode="json")
        body["projectId"] = rule.project_id
        try:
            result: dict[str, Any] = await self._alert_rules.upsert_item(body=body)
            return AlertRule.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_alert_rule failed for %s/%s: %s",
                rule.project_id, rule.id, exc.message,
            )
            raise

    async def delete_alert_rule(self, project_id: str, rule_id: str) -> None:
        """Delete an alert rule."""
        try:
            await self._alert_rules.delete_item(
                item=rule_id, partition_key=project_id,
            )
        except CosmosResourceNotFoundError:
            pass

    # ------------------------------------------------------------------
    # App registration operations
    # ------------------------------------------------------------------

    async def upsert_app_registration(
        self, tenant_id: str, app: AppRegistrationProfile,
    ) -> AppRegistrationProfile:
        """Insert or replace an app registration profile."""
        body = app.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._app_registrations.upsert_item(body=body)
            return AppRegistrationProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_app_registration failed for %s/%s: %s",
                tenant_id,
                app.id,
                exc.message,
            )
            raise

    async def get_app_registration(
        self, tenant_id: str, app_id: str,
    ) -> AppRegistrationProfile | None:
        """Point-read an app registration by tenant and app ID."""
        try:
            item: dict[str, Any] = await self._app_registrations.read_item(
                item=app_id,
                partition_key=tenant_id,
            )
            return AppRegistrationProfile.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_app_registrations(
        self, tenant_id: str, offset: int = 0, limit: int = 50,
    ) -> tuple[list[AppRegistrationProfile], int]:
        """List app registrations for a tenant with pagination.

        Returns (items, total_count).
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._app_registrations.query_items(
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
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[AppRegistrationProfile] = [
            AppRegistrationProfile.model_validate(item)
            async for item in self._app_registrations.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # MFA record operations
    # ------------------------------------------------------------------

    async def upsert_mfa_record(
        self, tenant_id: str, record: MfaRegistrationRecord,
    ) -> MfaRegistrationRecord:
        """Insert or replace an MFA registration record."""
        body = record.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._mfa_records.upsert_item(body=body)
            return MfaRegistrationRecord.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_mfa_record failed for %s/%s: %s",
                tenant_id,
                record.id,
                exc.message,
            )
            raise

    async def get_mfa_record(
        self, tenant_id: str, record_id: str,
    ) -> MfaRegistrationRecord | None:
        """Point-read an MFA record by tenant and record ID."""
        try:
            item: dict[str, Any] = await self._mfa_records.read_item(
                item=record_id,
                partition_key=tenant_id,
            )
            return MfaRegistrationRecord.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_mfa_records(
        self, tenant_id: str, offset: int = 0, limit: int = 50,
    ) -> tuple[list[MfaRegistrationRecord], int]:
        """List MFA registration records for a tenant with pagination.

        Returns (items, total_count).
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._mfa_records.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c.id OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[MfaRegistrationRecord] = [
            MfaRegistrationRecord.model_validate(item)
            async for item in self._mfa_records.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Conditional access policy operations
    # ------------------------------------------------------------------

    async def upsert_ca_policy(
        self, tenant_id: str, policy: ConditionalAccessPolicyRecord,
    ) -> ConditionalAccessPolicyRecord:
        """Insert or replace a conditional access policy record."""
        body = policy.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._ca_policies.upsert_item(body=body)
            return ConditionalAccessPolicyRecord.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_ca_policy failed for %s/%s: %s",
                tenant_id,
                policy.id,
                exc.message,
            )
            raise

    async def list_ca_policies(
        self, tenant_id: str,
    ) -> list[ConditionalAccessPolicyRecord]:
        """List all conditional access policies for a tenant."""
        query = "SELECT * FROM c WHERE c.tenantId = @tenantId"
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        return [
            ConditionalAccessPolicyRecord.model_validate(item)
            async for item in self._ca_policies.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]

    # ------------------------------------------------------------------
    # Risk detection operations
    # ------------------------------------------------------------------

    async def upsert_risk_detection(
        self, tenant_id: str, detection: dict[str, Any],
    ) -> None:
        """Insert or replace a risk detection summary (stored as raw dict)."""
        detection["tenantId"] = tenant_id
        try:
            await self._risk_detections.upsert_item(body=detection)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_risk_detection failed for %s/%s: %s",
                tenant_id,
                detection.get("id", "unknown"),
                exc.message,
            )
            raise

    async def list_risk_detections(
        self, tenant_id: str, limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List risk detection summaries for a tenant."""
        query = (
            "SELECT * FROM c WHERE c.tenantId = @tenantId"
            " ORDER BY c._ts DESC OFFSET 0 LIMIT @limit"
        )
        parameters: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@limit", "value": limit},
        ]
        return [
            item
            async for item in self._risk_detections.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    async def upsert_group(
        self, tenant_id: str, group: GroupProfile,
    ) -> GroupProfile:
        """Insert or replace a group profile."""
        body = group.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._groups.upsert_item(body=body)
            return GroupProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_group failed for %s/%s: %s",
                tenant_id,
                group.id,
                exc.message,
            )
            raise

    async def get_group(
        self, tenant_id: str, group_id: str,
    ) -> GroupProfile | None:
        """Point-read a group profile by tenant and group ID."""
        try:
            item: dict[str, Any] = await self._groups.read_item(
                item=group_id,
                partition_key=tenant_id,
            )
            return GroupProfile.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_groups(
        self, tenant_id: str, offset: int = 0, limit: int = 50,
    ) -> tuple[list[GroupProfile], int]:
        """List group profiles for a tenant with pagination.

        Returns (items, total_count).
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._groups.query_items(
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
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[GroupProfile] = [
            GroupProfile.model_validate(item)
            async for item in self._groups.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Access review operations
    # ------------------------------------------------------------------

    async def upsert_access_review(
        self, tenant_id: str, review: AccessReviewDefinition,
    ) -> AccessReviewDefinition:
        """Insert or replace an access review definition."""
        body = review.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._access_reviews.upsert_item(body=body)
            return AccessReviewDefinition.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_access_review failed for %s/%s: %s",
                tenant_id,
                review.id,
                exc.message,
            )
            raise

    async def list_access_reviews(
        self, tenant_id: str,
    ) -> list[AccessReviewDefinition]:
        """List all access review definitions for a tenant."""
        query = "SELECT * FROM c WHERE c.tenantId = @tenantId"
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        return [
            AccessReviewDefinition.model_validate(item)
            async for item in self._access_reviews.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]

    # ------------------------------------------------------------------
    # SoD rule operations
    # ------------------------------------------------------------------

    async def get_sod_rules(
        self, tenant_id: str,
    ) -> list[SodConflictRule]:
        """List all separation-of-duty conflict rules for a tenant."""
        query = "SELECT * FROM c WHERE c.tenantId = @tenantId"
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        return [
            SodConflictRule.model_validate(item)
            async for item in self._sod_rules.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]

    async def upsert_sod_rule(
        self, tenant_id: str, rule: SodConflictRule,
    ) -> SodConflictRule:
        """Insert or replace a separation-of-duty conflict rule."""
        body = rule.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._sod_rules.upsert_item(body=body)
            return SodConflictRule.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_sod_rule failed for %s/%s: %s",
                tenant_id,
                rule.id,
                exc.message,
            )
            raise

    async def delete_sod_rule(
        self, tenant_id: str, rule_id: str,
    ) -> None:
        """Delete a separation-of-duty conflict rule."""
        try:
            await self._sod_rules.delete_item(
                item=rule_id, partition_key=tenant_id,
            )
        except CosmosResourceNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Custom role operations
    # ------------------------------------------------------------------

    async def upsert_custom_role(
        self, tenant_id: str, role: CustomRoleProfile,
    ) -> CustomRoleProfile:
        """Insert or replace a custom role profile."""
        body = role.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._custom_roles.upsert_item(body=body)
            return CustomRoleProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_custom_role failed for %s/%s: %s",
                tenant_id,
                role.id,
                exc.message,
            )
            raise

    async def list_custom_roles(
        self, tenant_id: str,
    ) -> list[CustomRoleProfile]:
        """List all custom role profiles for a tenant."""
        query = "SELECT * FROM c WHERE c.tenantId = @tenantId"
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        return [
            CustomRoleProfile.model_validate(item)
            async for item in self._custom_roles.query_items(
                query=query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]

    # ------------------------------------------------------------------
    # Remediation action operations
    # ------------------------------------------------------------------

    async def create_remediation_action(
        self, tenant_id: str, action: RemediationAction,
    ) -> RemediationAction:
        """Insert a new remediation action."""
        body = action.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._remediation_actions.upsert_item(body=body)
            return RemediationAction.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos create_remediation_action failed for %s/%s: %s",
                tenant_id,
                action.id,
                exc.message,
            )
            raise

    async def get_remediation_action(
        self, tenant_id: str, action_id: str,
    ) -> RemediationAction | None:
        """Point-read a remediation action by tenant and action ID."""
        try:
            item: dict[str, Any] = await self._remediation_actions.read_item(
                item=action_id,
                partition_key=tenant_id,
            )
            return RemediationAction.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def update_remediation_status(
        self, tenant_id: str, action: RemediationAction,
    ) -> RemediationAction:
        """Update (upsert) a remediation action, typically to change its status."""
        body = action.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._remediation_actions.upsert_item(body=body)
            return RemediationAction.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos update_remediation_status failed for %s/%s: %s",
                tenant_id,
                action.id,
                exc.message,
            )
            raise

    async def list_remediation_actions(
        self, tenant_id: str, offset: int = 0, limit: int = 50,
    ) -> tuple[list[RemediationAction], int]:
        """List remediation actions for a tenant with pagination.

        Returns (items, total_count).
        """
        conditions = ["c.tenantId = @tenantId"]
        parameters: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        where_clause = " AND ".join(conditions)

        # Total count
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item
            async for item in self._remediation_actions.query_items(
                query=count_query,
                parameters=parameters,
                partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        # Paged results
        data_query = (
            f"SELECT * FROM c WHERE {where_clause}"
            f" ORDER BY c._ts DESC OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[RemediationAction] = [
            RemediationAction.model_validate(item)
            async for item in self._remediation_actions.query_items(
                query=data_query,
                parameters=data_params,
                partition_key=tenant_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # PIM Session operations
    # ------------------------------------------------------------------

    async def upsert_pim_session(
        self, tenant_id: str, session: PimSession,
    ) -> PimSession:
        body = session.model_dump(mode="json")
        body["tenantId"] = tenant_id
        result = await self._pim_sessions.upsert_item(body)
        return PimSession.model_validate(result)

    async def get_pim_session(
        self, tenant_id: str, session_id: str,
    ) -> PimSession | None:
        try:
            item: dict[str, Any] = await self._pim_sessions.read_item(
                item=session_id, partition_key=tenant_id,
            )
            return PimSession.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_pim_sessions(
        self,
        tenant_id: str,
        status: str | None = None,
        principal_id: str | None = None,
        role_name: str | None = None,
        has_anomalies: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PimSession], int]:
        conditions = ["c.tenantId = @tenantId"]
        params: list[dict[str, Any]] = [{"name": "@tenantId", "value": tenant_id}]

        if status:
            conditions.append("c.status = @status")
            params.append({"name": "@status", "value": status})
        if principal_id:
            conditions.append("c.principal_id = @principalId")
            params.append({"name": "@principalId", "value": principal_id})
        if role_name:
            conditions.append("c.role_name = @roleName")
            params.append({"name": "@roleName", "value": role_name})
        if has_anomalies is True:
            conditions.append("ARRAY_LENGTH(c.anomalies) > 0")
        elif has_anomalies is False:
            conditions.append("ARRAY_LENGTH(c.anomalies) = 0")

        where = " AND ".join(conditions)

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        count_results: list[int] = [
            item async for item in self._pim_sessions.query_items(
                query=count_query, parameters=params, partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c WHERE {where} "
            "ORDER BY c.activation_time DESC "
            "OFFSET @offset LIMIT @limit"
        )
        data_params = [
            *params,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[PimSession] = [
            PimSession.model_validate(item)
            async for item in self._pim_sessions.query_items(
                query=data_query, parameters=data_params, partition_key=tenant_id,
            )
        ]
        return items, total

    async def get_active_pim_sessions(
        self, tenant_id: str,
    ) -> list[PimSession]:
        query = (
            "SELECT * FROM c WHERE c.tenantId = @tenantId AND c.status = 'active' "
            "ORDER BY c.activation_time DESC"
        )
        params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        return [
            PimSession.model_validate(item)
            async for item in self._pim_sessions.query_items(
                query=query, parameters=params, partition_key=tenant_id,
            )
        ]

    async def get_pim_sessions_for_identity(
        self, tenant_id: str, identity_id: str, offset: int = 0, limit: int = 20,
    ) -> tuple[list[PimSession], int]:
        base_where = "c.tenantId = @tenantId AND c.identity_id = @identityId"
        params: list[dict[str, str]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@identityId", "value": identity_id},
        ]

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {base_where}"
        count_results: list[int] = [
            item async for item in self._pim_sessions.query_items(
                query=count_query, parameters=params, partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c WHERE {base_where} "
            "ORDER BY c.activation_time DESC "
            "OFFSET @offset LIMIT @limit"
        )
        data_params: list[dict[str, Any]] = [
            *params,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[PimSession] = [
            PimSession.model_validate(item)
            async for item in self._pim_sessions.query_items(
                query=data_query, parameters=data_params, partition_key=tenant_id,
            )
        ]
        return items, total

    async def get_pim_session_analytics(
        self, tenant_id: str, days: int = 30,
    ) -> dict[str, Any]:
        from collections import Counter
        from datetime import UTC, timedelta

        now = datetime.now(UTC)
        cutoff = (now - timedelta(days=days)).isoformat()
        params: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@cutoff", "value": cutoff},
        ]
        base_where = "c.tenantId = @tenantId AND c.activation_time >= @cutoff"

        all_query = f"SELECT * FROM c WHERE {base_where}"
        sessions: list[dict[str, Any]] = [
            item async for item in self._pim_sessions.query_items(
                query=all_query, parameters=params, partition_key=tenant_id,
            )
        ]

        total = len(sessions)
        active = sum(1 for s in sessions if s.get("status") == "active")
        expired = sum(1 for s in sessions if s.get("status") == "expired")
        with_anomalies = sum(1 for s in sessions if len(s.get("anomalies", [])) > 0)

        durations = [s.get("duration_minutes", 0) for s in sessions]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        role_counter: Counter[str] = Counter()
        activator_counter: Counter[str] = Counter()
        hour_counter: Counter[int] = Counter()
        day_counter: Counter[str] = Counter()
        anomaly_type_counter: Counter[str] = Counter()

        for s in sessions:
            role_counter[s.get("role_name", "Unknown")] += 1
            activator_counter[s.get("principal_display_name", "Unknown")] += 1

            act_time = s.get("activation_time", "")
            if isinstance(act_time, str) and len(act_time) >= 13:
                try:
                    dt = datetime.fromisoformat(act_time.replace("Z", "+00:00"))
                    hour_counter[dt.hour] += 1
                    day_counter[dt.strftime("%Y-%m-%d")] += 1
                except (ValueError, TypeError):
                    pass

            for a in s.get("anomalies", []):
                anomaly_type_counter[a.get("anomaly_type", "unknown")] += 1

        return {
            "tenant_id": tenant_id,
            "total_sessions": total,
            "active_sessions": active,
            "expired_sessions": expired,
            "sessions_with_anomalies": with_anomalies,
            "avg_session_duration_minutes": round(avg_duration, 1),
            "top_activated_roles": [
                {"role_name": name, "count": cnt}
                for name, cnt in role_counter.most_common(10)
            ],
            "top_activators": [
                {"principal_display_name": name, "count": cnt}
                for name, cnt in activator_counter.most_common(10)
            ],
            "activations_by_hour": dict(hour_counter),
            "activations_by_day": [
                {"date": d, "count": c}
                for d, c in sorted(day_counter.items())
            ],
            "anomaly_counts_by_type": dict(anomaly_type_counter),
            "computed_at": now.isoformat(),
        }

    async def get_session_action_events(
        self, tenant_id: str, identity_id: str,
        start: datetime, end: datetime,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[ActionEvent], int]:
        where = (
            "c.tenantId = @tenantId AND c.identity_id = @identityId "
            "AND c.timestamp >= @start AND c.timestamp <= @end"
        )
        params: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@identityId", "value": identity_id},
            {"name": "@start", "value": start.isoformat()},
            {"name": "@end", "value": end.isoformat()},
        ]

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        count_results: list[int] = [
            item async for item in self._action_events.query_items(
                query=count_query, parameters=params, partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c WHERE {where} "
            "ORDER BY c.timestamp ASC "
            "OFFSET @offset LIMIT @limit"
        )
        data_params = [
            *params,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[ActionEvent] = [
            ActionEvent.model_validate(item)
            async for item in self._action_events.query_items(
                query=data_query, parameters=data_params, partition_key=tenant_id,
            )
        ]
        return items, total

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
            "projects": self._projects,
            "project_members": self._project_members,
            "scan_history": self._scan_history,
            "scan_schedules": self._scan_schedules,
            "alert_rules": self._alert_rules,
            "app_registrations": self._app_registrations,
            "mfa_records": self._mfa_records,
            "ca_policies": self._ca_policies,
            "risk_detections": self._risk_detections,
            "groups": self._groups,
            "access_reviews": self._access_reviews,
            "sod_rules": self._sod_rules,
            "custom_roles": self._custom_roles,
            "remediation_actions": self._remediation_actions,
            "pim_sessions": self._pim_sessions,
            "access_path_analyses": self._access_path_analyses,
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
    # Analytics aggregation helpers
    # ------------------------------------------------------------------

    async def get_analytics_data(self, tenant_id: str, days: int = 30) -> dict[str, Any]:
        """Run cross-container aggregation queries for the Analytics page."""
        from collections import Counter
        from datetime import UTC, datetime, timedelta

        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        base_params: list[dict[str, Any]] = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@cutoff", "value": cutoff},
        ]

        # --- action_events: totals ---
        totals_query = (
            "SELECT VALUE {"
            "  total: COUNT(1),"
            "  failures: COUNT(c.result = 'failure' ? 1 : undefined)"
            "} FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff"
        )
        totals_results: list[dict[str, Any]] = [
            item async for item in self._action_events.query_items(
                query=totals_query, parameters=base_params, partition_key=tenant_id,
            )
        ]
        total_actions = totals_results[0].get("total", 0) if totals_results else 0
        failures = totals_results[0].get("failures", 0) if totals_results else 0
        failed_action_pct = (failures / total_actions * 100.0) if total_actions > 0 else 0.0

        # --- action_events: unique active identities ---
        unique_query = (
            "SELECT VALUE COUNT(1) FROM "
            "(SELECT DISTINCT c.identity_id FROM c "
            "WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff)"
        )
        unique_results: list[int] = [
            item async for item in self._action_events.query_items(
                query=unique_query, parameters=base_params, partition_key=tenant_id,
            )
        ]
        unique_active = unique_results[0] if unique_results else 0
        avg_actions = (total_actions / unique_active) if unique_active > 0 else 0.0

        # --- action_events: daily action counts ---
        daily_query = (
            "SELECT SUBSTRING(c.timestamp, 0, 10) AS date, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "GROUP BY SUBSTRING(c.timestamp, 0, 10)"
        )
        daily_action_counts: list[dict[str, Any]] = []
        async for item in self._action_events.query_items(
            query=daily_query, parameters=base_params, partition_key=tenant_id,
        ):
            daily_action_counts.append({
                "date": item.get("date", ""),
                "value": float(item.get("cnt", 0)),
            })
        daily_action_counts.sort(key=lambda x: x["date"])

        # --- action_events: top actions ---
        top_actions_query = (
            "SELECT c.action, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "GROUP BY c.action"
        )
        top_actions_raw: list[dict[str, Any]] = [
            item async for item in self._action_events.query_items(
                query=top_actions_query, parameters=base_params, partition_key=tenant_id,
            )
        ]
        top_actions_raw.sort(key=lambda x: x.get("cnt", 0), reverse=True)
        top_actions = [
            {"action": r.get("action", ""), "count": r.get("cnt", 0)}
            for r in top_actions_raw[:10]
        ]

        # --- action_events: most active identities ---
        active_query = (
            "SELECT c.identity_id, c.identity_display_name, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "GROUP BY c.identity_id, c.identity_display_name"
        )
        active_raw: list[dict[str, Any]] = [
            item async for item in self._action_events.query_items(
                query=active_query, parameters=base_params, partition_key=tenant_id,
            )
        ]
        active_raw.sort(key=lambda x: x.get("cnt", 0), reverse=True)
        most_active = [
            {
                "identity_id": r.get("identity_id", ""),
                "display_name": r.get("identity_display_name", ""),
                "identity_type": r.get("identity_id", "").split("_")[0] if "_" in r.get("identity_id", "") else "User",
                "count": r.get("cnt", 0),
            }
            for r in active_raw[:10]
        ]

        # --- action_events: by source ---
        source_query = (
            "SELECT c.source, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "GROUP BY c.source"
        )
        actions_by_source: dict[str, int] = {}
        async for item in self._action_events.query_items(
            query=source_query, parameters=base_params, partition_key=tenant_id,
        ):
            actions_by_source[item.get("source", "unknown")] = item.get("cnt", 0)

        # --- action_events: success vs failure ---
        result_query = (
            "SELECT c.result, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "GROUP BY c.result"
        )
        success_vs_failure: dict[str, int] = {}
        async for item in self._action_events.query_items(
            query=result_query, parameters=base_params, partition_key=tenant_id,
        ):
            success_vs_failure[item.get("result", "unknown")] = item.get("cnt", 0)

        # --- action_events: top resources ---
        resource_query = (
            "SELECT c.resource, c.resource_type, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.timestamp >= @cutoff "
            "AND c.resource != null "
            "GROUP BY c.resource, c.resource_type"
        )
        resource_raw: list[dict[str, Any]] = [
            item async for item in self._action_events.query_items(
                query=resource_query, parameters=base_params, partition_key=tenant_id,
            )
        ]
        resource_raw.sort(key=lambda x: x.get("cnt", 0), reverse=True)
        top_resources = [
            {
                "resource": r.get("resource", ""),
                "resource_type": r.get("resource_type", ""),
                "count": r.get("cnt", 0),
            }
            for r in resource_raw[:10]
        ]

        # --- identity_profiles: roles (flatten in Python) ---
        roles_query = (
            "SELECT c.current_roles FROM c WHERE c.tenantId = @tenantId"
        )
        roles_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        role_counter: Counter[str] = Counter()
        permanent_count = 0
        pim_count = 0
        async for item in self._identity_profiles.query_items(
            query=roles_query, parameters=roles_params, partition_key=tenant_id,
        ):
            for role in item.get("current_roles", []):
                role_counter[role.get("role_name", "Unknown")] += 1
                if role.get("is_permanent", True):
                    permanent_count += 1
                else:
                    pim_count += 1
        top_roles = [
            {"role_name": name, "count": cnt}
            for name, cnt in role_counter.most_common(10)
        ]

        # --- identity_profiles: stale identities ---
        now = datetime.now(UTC)
        stale_counts: dict[str, int] = {}
        for label, threshold_days in [("30d", 30), ("60d", 60), ("90d", 90)]:
            threshold = (now - timedelta(days=threshold_days)).isoformat()
            stale_query = (
                "SELECT VALUE COUNT(1) FROM c "
                "WHERE c.tenantId = @tenantId AND c.last_seen < @threshold"
            )
            stale_params: list[dict[str, Any]] = [
                {"name": "@tenantId", "value": tenant_id},
                {"name": "@threshold", "value": threshold},
            ]
            results: list[int] = [
                item async for item in self._identity_profiles.query_items(
                    query=stale_query, parameters=stale_params, partition_key=tenant_id,
                )
            ]
            stale_counts[label] = results[0] if results else 0

        # --- identity_profiles: new identities ---
        new_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.tenantId = @tenantId AND c.first_seen >= @cutoff"
        )
        new_results: list[int] = [
            item async for item in self._identity_profiles.query_items(
                query=new_query, parameters=base_params, partition_key=tenant_id,
            )
        ]
        new_identities_count = new_results[0] if new_results else 0

        # --- role_recommendations: permission utilization ---
        perm_query = (
            "SELECT c.permission_gaps FROM c WHERE c.tenantId = @tenantId"
        )
        perm_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        used_count = 0
        unused_count = 0
        async for item in self._role_recommendations.query_items(
            query=perm_query, parameters=perm_params, partition_key=tenant_id,
        ):
            for gap in item.get("permission_gaps", []):
                if gap.get("is_used", False):
                    used_count += 1
                else:
                    unused_count += 1

        # --- role_recommendations: overprivileged count ---
        overpriv_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.tenantId = @tenantId AND c.reduction_score > 30"
        )
        overpriv_results: list[int] = [
            item async for item in self._role_recommendations.query_items(
                query=overpriv_query, parameters=perm_params, partition_key=tenant_id,
            )
        ]
        overprivileged_count = overpriv_results[0] if overpriv_results else 0

        # --- best_practice_violations: by type ---
        vtype_query = (
            "SELECT c.violation_type, COUNT(1) AS cnt "
            "FROM c WHERE c.tenantId = @tenantId AND c.resolved = false "
            "GROUP BY c.violation_type"
        )
        vtype_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        violations_by_type: dict[str, int] = {}
        async for item in self._best_practice_violations.query_items(
            query=vtype_query, parameters=vtype_params, partition_key=tenant_id,
        ):
            violations_by_type[item.get("violation_type", "unknown")] = item.get("cnt", 0)

        # --- best_practice_violations: credential expiry ---
        cred_query = (
            "SELECT c.identity_id, c.identity_display_name, c.detected_at "
            "FROM c WHERE c.tenantId = @tenantId "
            "AND c.violation_type = 'sp_credential_expiry' AND c.resolved = false "
            "ORDER BY c.detected_at DESC OFFSET 0 LIMIT 10"
        )
        credential_expiry: list[dict[str, str]] = [
            {
                "identity_id": item.get("identity_id", ""),
                "identity_display_name": item.get("identity_display_name", ""),
                "detected_at": item.get("detected_at", ""),
            }
            async for item in self._best_practice_violations.query_items(
                query=cred_query, parameters=vtype_params, partition_key=tenant_id,
            )
        ]

        # --- drift_alerts: recent 5 ---
        drift_query = (
            "SELECT * FROM c WHERE c.tenantId = @tenantId "
            "ORDER BY c.detected_at DESC OFFSET 0 LIMIT 5"
        )
        drift_params: list[dict[str, str]] = [{"name": "@tenantId", "value": tenant_id}]
        recent_drift: list[dict[str, Any]] = [
            item async for item in self._drift_alerts.query_items(
                query=drift_query, parameters=drift_params, partition_key=tenant_id,
            )
        ]

        return {
            "total_actions": total_actions,
            "unique_active_identities": unique_active,
            "avg_actions_per_identity": round(avg_actions, 1),
            "failed_action_pct": round(failed_action_pct, 1),
            "new_identities_count": new_identities_count,
            "daily_action_counts": daily_action_counts,
            "top_actions": top_actions,
            "most_active_identities": most_active,
            "actions_by_source": actions_by_source,
            "success_vs_failure": success_vs_failure,
            "top_resources": top_resources,
            "top_roles": top_roles,
            "permission_utilization": {"used": used_count, "unused": unused_count},
            "permanent_vs_pim": {"permanent": permanent_count, "pim": pim_count},
            "overprivileged_count": overprivileged_count,
            "violations_by_type": violations_by_type,
            "stale_identity_counts": stale_counts,
            "credential_expiry_violations": credential_expiry,
            "recent_drift_alerts": recent_drift,
        }

    # ------------------------------------------------------------------
    # Access Path Analyses
    # ------------------------------------------------------------------

    async def upsert_access_path_analysis(
        self, tenant_id: str, analysis: AccessPathAnalysis,
    ) -> AccessPathAnalysis:
        body = analysis.model_dump(mode="json")
        body["tenantId"] = tenant_id
        try:
            result: dict[str, Any] = await self._access_path_analyses.upsert_item(body=body)
            return AccessPathAnalysis.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_access_path_analysis failed for %s/%s: %s",
                tenant_id, analysis.id, exc,
            )
            raise

    async def get_access_path_analysis_by_identity(
        self, tenant_id: str, identity_id: str,
    ) -> AccessPathAnalysis | None:
        query = (
            "SELECT * FROM c WHERE c.tenantId = @tid AND c.identity_id = @iid"
        )
        params: list[dict[str, str]] = [
            {"name": "@tid", "value": tenant_id},
            {"name": "@iid", "value": identity_id},
        ]
        items: list[AccessPathAnalysis] = [
            AccessPathAnalysis.model_validate(item)
            async for item in self._access_path_analyses.query_items(
                query=query, parameters=params, partition_key=tenant_id,
            )
        ]
        return items[0] if items else None

    async def list_access_path_analyses(
        self, tenant_id: str, min_risk: str | None = None,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[AccessPathAnalysis], int]:
        where = "c.tenantId = @tid AND c.total_paths > 0"
        params: list[dict[str, str]] = [{"name": "@tid", "value": tenant_id}]

        if min_risk:
            risk_order = {"critical": 1, "high": 2, "medium": 3}
            allowed = [k for k, v in risk_order.items() if v <= risk_order.get(min_risk, 3)]
            placeholders = ", ".join(f"'{r}'" for r in allowed)
            where += f" AND c.highest_risk IN ({placeholders})"

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        count_results: list[int] = [
            item async for item in self._access_path_analyses.query_items(
                query=count_query, parameters=params, partition_key=tenant_id,
            )
        ]
        total = count_results[0] if count_results else 0

        query = (
            f"SELECT * FROM c WHERE {where} "
            "ORDER BY c.critical_paths DESC, c.high_paths DESC "
            f"OFFSET {offset} LIMIT {limit}"
        )
        items: list[AccessPathAnalysis] = [
            AccessPathAnalysis.model_validate(item)
            async for item in self._access_path_analyses.query_items(
                query=query, parameters=params, partition_key=tenant_id,
            )
        ]
        return items, total

    async def get_access_path_summary(self, tenant_id: str) -> AccessPathSummary:
        query = (
            "SELECT VALUE {"
            "  total: COUNT(1),"
            "  critical: COUNT(c.highest_risk = 'critical' ? 1 : undefined),"
            "  high: COUNT(c.highest_risk = 'high' ? 1 : undefined),"
            "  medium: COUNT(c.highest_risk = 'medium' ? 1 : undefined)"
            "} FROM c WHERE c.tenantId = @tid AND c.total_paths > 0"
        )
        params: list[dict[str, str]] = [{"name": "@tid", "value": tenant_id}]
        results: list[dict[str, Any]] = [
            item async for item in self._access_path_analyses.query_items(
                query=query, parameters=params, partition_key=tenant_id,
            )
        ]
        row = results[0] if results else {}
        return AccessPathSummary(
            total_identities_with_paths=row.get("total", 0),
            critical_count=row.get("critical", 0),
            high_count=row.get("high", 0),
            medium_count=row.get("medium", 0),
        )

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
