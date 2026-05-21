from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

from azure.cosmos.aio import ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from app.models.access_path import AccessPathAnalysis, AccessPathSummary
from app.models.access_review import AccessReviewDefinition
from app.models.action import ActionEvent
from app.models.app_registration import AppRegistrationProfile
from app.models.best_practice import BestPracticeViolation
from app.models.conditional_access import ConditionalAccessPolicyRecord
from app.models.custom_role import CustomRoleProfile
from app.models.drift import BaselineStats, DriftAlert
from app.models.group import GroupProfile
from app.models.identity import IdentityProfile
from app.models.mfa_status import MfaRegistrationRecord
from app.models.narrative import Narrative
from app.models.pim_session import PimSession
from app.models.project import ScanLogEntry
from app.models.remediation import RemediationAction
from app.models.role import RoleRecommendation
from app.models.sod_policy import SodConflictRule
from app.models.tenant import TenantConfig
from app.services.batch_writer import BatchWriter

logger = logging.getLogger(__name__)


class ProjectRepo:
    """Repository for a single project's Cosmos DB database.

    All data is isolated at the database level — no tenant_id filtering needed.
    """

    def __init__(
        self,
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
        scan_events: ContainerProxy,
    ) -> None:
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
        self._scan_events = scan_events
        self._total_ru: float = 0.0
        self._op_count: int = 0

    def _log_op(
        self,
        op: str,
        container: str,
        *,
        items: int = 1,
        duration_ms: float | None = None,
        ru: float | None = None,
    ) -> None:
        if ru is not None:
            self._total_ru += ru
        self._op_count += 1
        extra = ""
        if duration_ms is not None:
            extra += f" duration={duration_ms:.0f}ms"
        if ru is not None:
            extra += f" ru={ru:.2f}"
        if items > 1:
            extra += f" items={items}"
        logger.debug("ProjectRepo.%s [%s]%s", op, container, extra)

    @property
    def total_ru(self) -> float:
        return self._total_ru

    @property
    def op_count(self) -> int:
        return self._op_count

    def reset_ru_tracking(self) -> None:
        self._total_ru = 0.0
        self._op_count = 0

    @classmethod
    async def create(cls, db: DatabaseProxy) -> ProjectRepo:
        """Factory that gets container clients from an existing project database.

        Containers are provisioned by ProjectDatabaseManager — this only gets handles.
        """
        return cls(
            db=db,
            tenant_configs=db.get_container_client("tenant_configs"),
            identity_profiles=db.get_container_client("identity_profiles"),
            action_events=db.get_container_client("action_events"),
            sync_state=db.get_container_client("sync_state"),
            role_recommendations=db.get_container_client("role_recommendations"),
            drift_alerts=db.get_container_client("drift_alerts"),
            baselines=db.get_container_client("baselines"),
            best_practice_violations=db.get_container_client("best_practice_violations"),
            narratives=db.get_container_client("narratives"),
            app_registrations=db.get_container_client("app_registrations"),
            mfa_records=db.get_container_client("mfa_records"),
            ca_policies=db.get_container_client("ca_policies"),
            risk_detections=db.get_container_client("risk_detections"),
            groups=db.get_container_client("groups"),
            access_reviews=db.get_container_client("access_reviews"),
            sod_rules=db.get_container_client("sod_rules"),
            custom_roles=db.get_container_client("custom_roles"),
            remediation_actions=db.get_container_client("remediation_actions"),
            pim_sessions=db.get_container_client("pim_sessions"),
            access_path_analyses=db.get_container_client("access_path_analyses"),
            scan_events=db.get_container_client("scan_events"),
        )

    # ------------------------------------------------------------------
    # Internal helpers for logging + RU tracking
    # ------------------------------------------------------------------

    async def _tracked_upsert(
        self,
        container: ContainerProxy,
        body: dict[str, Any],
        op_name: str,
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        ru: float = 0.0

        def _hook(headers: dict[str, str], _: Any) -> None:
            nonlocal ru
            ru = float(headers.get("x-ms-request-charge", 0))

        result: dict[str, Any] = await container.upsert_item(
            body=body, response_hook=_hook,
        )
        elapsed = (time.monotonic() - t0) * 1000
        self._log_op(op_name, container.id, duration_ms=elapsed, ru=ru)
        return result

    async def _tracked_read(
        self,
        container: ContainerProxy,
        item_id: str,
        partition_key: str,
        op_name: str,
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        ru: float = 0.0

        def _hook(headers: dict[str, str], _: Any) -> None:
            nonlocal ru
            ru = float(headers.get("x-ms-request-charge", 0))

        result: dict[str, Any] = await container.read_item(
            item=item_id, partition_key=partition_key, response_hook=_hook,
        )
        elapsed = (time.monotonic() - t0) * 1000
        self._log_op(op_name, container.id, duration_ms=elapsed, ru=ru)
        return result

    async def _tracked_query(
        self,
        container: ContainerProxy,
        query: str,
        parameters: list[dict[str, Any]],
        op_name: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        t0 = time.monotonic()
        ru: float = 0.0

        def _hook(headers: dict[str, str], _: Any) -> None:
            nonlocal ru
            ru += float(headers.get("x-ms-request-charge", 0))

        results: list[dict[str, Any]] = [
            item async for item in container.query_items(
                query=query, parameters=parameters,
                response_hook=_hook, **kwargs,
            )
        ]
        elapsed = (time.monotonic() - t0) * 1000
        self._log_op(op_name, container.id, items=len(results), duration_ms=elapsed, ru=ru)
        return results

    # ------------------------------------------------------------------
    # Tenant config operations (PK: /id)
    # ------------------------------------------------------------------

    async def get_tenant_config(self, config_id: str) -> TenantConfig | None:
        try:
            item = await self._tracked_read(
                self._tenant_configs, config_id, config_id, "get_tenant_config",
            )
            return TenantConfig.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_tenant_config(self, config: TenantConfig) -> TenantConfig:
        body = config.model_dump(mode="json")
        try:
            result = await self._tracked_upsert(
                self._tenant_configs, body, "upsert_tenant_config",
            )
            return TenantConfig.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_tenant_config failed for %s: %s", config.id, exc.message)
            raise

    # ------------------------------------------------------------------
    # Identity profile operations (PK: /id)
    # ------------------------------------------------------------------

    async def get_identity(self, identity_id: str) -> IdentityProfile | None:
        try:
            item = await self._tracked_read(
                self._identity_profiles, identity_id, identity_id, "get_identity",
            )
            return IdentityProfile.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_identity(self, profile: IdentityProfile) -> IdentityProfile:
        body = profile.model_dump(mode="json")
        try:
            result = await self._tracked_upsert(
                self._identity_profiles, body, "upsert_identity",
            )
            return IdentityProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_identity failed for %s: %s", profile.id, exc.message)
            raise

    async def list_identities(
        self,
        identity_type: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[IdentityProfile], int]:
        conditions: list[str] = []
        parameters: list[dict[str, Any]] = []

        if identity_type is not None:
            conditions.append("c.identity_type = @identityType")
            parameters.append({"name": "@identityType", "value": identity_type})

        if search is not None:
            conditions.append(
                "(CONTAINS(LOWER(c.display_name), LOWER(@search))"
                " OR CONTAINS(LOWER(c.upn), LOWER(@search)))"
            )
            parameters.append({"name": "@search", "value": search})

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = f"SELECT VALUE COUNT(1) FROM c{where_clause}"
        count_results = await self._tracked_query(
            self._identity_profiles, count_query, parameters, "list_identities.count",
        )
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c{where_clause}"
            f" ORDER BY c.display_name OFFSET @offset LIMIT @limit"
        )
        data_params = [
            *parameters,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        raw_items = await self._tracked_query(
            self._identity_profiles, data_query, data_params, "list_identities",
        )
        items = [IdentityProfile.model_validate(item) for item in raw_items]
        return items, total

    async def batch_upsert_identities(self, profiles: list[IdentityProfile]) -> int:
        writer = BatchWriter(self._identity_profiles, "id")
        for p in profiles:
            writer.add(p.model_dump(mode="json"))
        return await writer.flush()

    # ------------------------------------------------------------------
    # Action event operations (PK: /identity_id)
    # ------------------------------------------------------------------

    async def append_action_events(self, events: list[ActionEvent]) -> int:
        writer = BatchWriter(self._action_events, "identity_id")
        for event in events:
            writer.add(event.model_dump(mode="json"))
            if writer.should_flush:
                await writer.flush()
        return await writer.flush()

    async def load_all_action_events(
        self,
        since: datetime | None = None,
    ) -> list[ActionEvent]:
        return [event async for event in self.stream_action_events(since=since)]

    async def stream_action_events(
        self,
        since: datetime | None = None,
    ) -> AsyncGenerator[ActionEvent, None]:
        """Yield action events one at a time to avoid loading all into memory."""
        conditions: list[str] = []
        parameters: list[dict[str, Any]] = []
        if since is not None:
            conditions.append("c.timestamp >= @since")
            parameters.append({"name": "@since", "value": since.isoformat()})
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM c{where} ORDER BY c.timestamp ASC"
        async for item in self._action_events.query_items(
            query=query, parameters=parameters,
        ):
            yield ActionEvent.model_validate(item)

    async def list_actions(
        self,
        identity_id: str,
        start: datetime | None = None,
        end: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ActionEvent], int]:
        conditions = ["c.identity_id = @identityId"]
        parameters: list[dict[str, Any]] = [
            {"name": "@identityId", "value": identity_id},
        ]

        if start is not None:
            conditions.append("c.timestamp >= @start")
            parameters.append({"name": "@start", "value": start.isoformat()})
        if end is not None:
            conditions.append("c.timestamp <= @end")
            parameters.append({"name": "@end", "value": end.isoformat()})

        where_clause = " AND ".join(conditions)

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_results: list[int] = [
            item async for item in self._action_events.query_items(
                query=count_query, parameters=parameters,
                partition_key=identity_id,
            )
        ]
        total = count_results[0] if count_results else 0

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
                query=data_query, parameters=data_params,
                partition_key=identity_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Role recommendation operations (PK: /identity_id)
    # ------------------------------------------------------------------

    async def get_recommendation(self, identity_id: str) -> RoleRecommendation | None:
        try:
            item = await self._tracked_read(
                self._role_recommendations, identity_id, identity_id, "get_recommendation",
            )
            return RoleRecommendation.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_recommendation(self, rec: RoleRecommendation) -> RoleRecommendation:
        body = rec.model_dump(mode="json")
        try:
            result = await self._tracked_upsert(
                self._role_recommendations, body, "upsert_recommendation",
            )
            return RoleRecommendation.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_recommendation failed for %s: %s", rec.identity_id, exc.message)
            raise

    async def list_recommendations(
        self,
        identity_type: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RoleRecommendation], int]:
        conditions: list[str] = []
        parameters: list[dict[str, Any]] = []

        if identity_type is not None:
            conditions.append("c.identity_type = @identityType")
            parameters.append({"name": "@identityType", "value": identity_type})

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = f"SELECT VALUE COUNT(1) FROM c{where_clause}"
        count_results: list[int] = [
            item async for item in self._role_recommendations.query_items(
                query=count_query, parameters=parameters,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c{where_clause}"
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
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    async def batch_upsert_recommendations(self, recs: list[RoleRecommendation]) -> int:
        writer = BatchWriter(self._role_recommendations, "identity_id")
        for r in recs:
            writer.add(r.model_dump(mode="json"))
        return await writer.flush()

    # ------------------------------------------------------------------
    # Drift alert operations (PK: /identity_id)
    # ------------------------------------------------------------------

    async def get_drift_alert(self, alert_id: str) -> DriftAlert | None:
        query = "SELECT * FROM c WHERE c.id = @id"
        params: list[dict[str, str]] = [{"name": "@id", "value": alert_id}]
        items: list[DriftAlert] = [
            DriftAlert.model_validate(item)
            async for item in self._drift_alerts.query_items(
                query=query, parameters=params,
            )
        ]
        return items[0] if items else None

    async def upsert_drift_alert(self, alert: DriftAlert) -> DriftAlert:
        body = alert.model_dump(mode="json")
        try:
            result = await self._tracked_upsert(
                self._drift_alerts, body, "upsert_drift_alert",
            )
            return DriftAlert.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_drift_alert failed for %s: %s", alert.id, exc.message)
            raise

    async def list_drift_alerts(
        self,
        severity: str | None = None,
        drift_status: str | None = None,
        identity_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DriftAlert], int]:
        conditions: list[str] = []
        parameters: list[dict[str, Any]] = []

        if severity is not None:
            conditions.append("c.severity = @severity")
            parameters.append({"name": "@severity", "value": severity})
        if drift_status is not None:
            conditions.append("c.status = @driftStatus")
            parameters.append({"name": "@driftStatus", "value": drift_status})
        if identity_id is not None:
            conditions.append("c.identity_id = @identityId")
            parameters.append({"name": "@identityId", "value": identity_id})

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = f"SELECT VALUE COUNT(1) FROM c{where_clause}"
        count_results: list[int] = [
            item async for item in self._drift_alerts.query_items(
                query=count_query, parameters=parameters,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c{where_clause}"
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
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    async def batch_upsert_drift_alerts(self, alerts: list[DriftAlert]) -> int:
        writer = BatchWriter(self._drift_alerts, "identity_id")
        for a in alerts:
            writer.add(a.model_dump(mode="json"))
        return await writer.flush()

    # ------------------------------------------------------------------
    # Baseline operations (PK: /identity_id)
    # ------------------------------------------------------------------

    async def upsert_baseline(self, baseline: BaselineStats) -> BaselineStats:
        body = baseline.model_dump(mode="json")
        try:
            result = await self._tracked_upsert(
                self._baselines, body, "upsert_baseline",
            )
            return BaselineStats.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_baseline failed for %s: %s", baseline.id, exc.message)
            raise

    async def list_baselines(self, identity_id: str) -> list[BaselineStats]:
        query = "SELECT * FROM c WHERE c.identity_id = @identityId"
        parameters: list[dict[str, str]] = [
            {"name": "@identityId", "value": identity_id},
        ]
        return [
            BaselineStats.model_validate(item)
            async for item in self._baselines.query_items(
                query=query, parameters=parameters,
                partition_key=identity_id,
            )
        ]

    async def batch_upsert_baselines(self, baselines: list[BaselineStats]) -> int:
        writer = BatchWriter(self._baselines, "identity_id")
        for b in baselines:
            writer.add(b.model_dump(mode="json"))
        return await writer.flush()

    # ------------------------------------------------------------------
    # Best practice violation operations (PK: /id)
    # ------------------------------------------------------------------

    async def get_violation(self, violation_id: str) -> BestPracticeViolation | None:
        try:
            item: dict[str, Any] = await self._best_practice_violations.read_item(
                item=violation_id, partition_key=violation_id,
            )
            return BestPracticeViolation.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_violation(self, violation: BestPracticeViolation) -> BestPracticeViolation:
        body = violation.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._best_practice_violations.upsert_item(body=body)
            return BestPracticeViolation.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_violation failed for %s: %s", violation.id, exc.message)
            raise

    async def list_violations(
        self,
        violation_type: str | None = None,
        priority: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[BestPracticeViolation], int]:
        conditions: list[str] = []
        parameters: list[dict[str, Any]] = []

        if violation_type is not None:
            conditions.append("c.violation_type = @violationType")
            parameters.append({"name": "@violationType", "value": violation_type})
        if priority is not None:
            conditions.append("c.priority = @priority")
            parameters.append({"name": "@priority", "value": priority})

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = f"SELECT VALUE COUNT(1) FROM c{where_clause}"
        count_results: list[int] = [
            item async for item in self._best_practice_violations.query_items(
                query=count_query, parameters=parameters,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c{where_clause}"
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
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    async def batch_upsert_violations(self, violations: list[BestPracticeViolation]) -> int:
        writer = BatchWriter(self._best_practice_violations, "id")
        for v in violations:
            writer.add(v.model_dump(mode="json"))
        return await writer.flush()

    # ------------------------------------------------------------------
    # Sync state operations (PK: /id)
    # ------------------------------------------------------------------

    async def get_sync_state(self, sync_type: str) -> dict[str, Any] | None:
        doc_id = sync_type
        try:
            item: dict[str, Any] = await self._sync_state.read_item(
                item=doc_id, partition_key=doc_id,
            )
            return item
        except CosmosResourceNotFoundError:
            return None

    async def upsert_sync_state(self, sync_type: str, state: dict[str, Any]) -> None:
        body = {
            "id": sync_type,
            "sync_type": sync_type,
            **state,
        }
        try:
            await self._sync_state.upsert_item(body=body)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_sync_state failed for %s: %s", sync_type, exc.message)
            raise

    async def list_sync_states_by_prefix(self, prefix: str) -> list[dict[str, Any]]:
        query = "SELECT * FROM c WHERE STARTSWITH(c.sync_type, @prefix)"
        parameters: list[dict[str, str]] = [{"name": "@prefix", "value": prefix}]
        return [
            item async for item in self._sync_state.query_items(
                query=query, parameters=parameters,
            )
        ]

    # ------------------------------------------------------------------
    # Narrative operations (PK: /id)
    # ------------------------------------------------------------------

    async def get_narrative(self, narrative_id: str) -> Narrative | None:
        try:
            item: dict[str, Any] = await self._narratives.read_item(
                item=narrative_id, partition_key=narrative_id,
            )
            return Narrative.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_narrative(self, narrative: Narrative) -> Narrative:
        body = narrative.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._narratives.upsert_item(body=body)
            return Narrative.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_narrative failed for %s: %s", narrative.id, exc.message)
            raise

    # ------------------------------------------------------------------
    # App registration operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_app_registration(self, app: AppRegistrationProfile) -> AppRegistrationProfile:
        body = app.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._app_registrations.upsert_item(body=body)
            return AppRegistrationProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_app_registration failed for %s: %s", app.id, exc.message)
            raise

    async def get_app_registration(self, app_id: str) -> AppRegistrationProfile | None:
        try:
            item: dict[str, Any] = await self._app_registrations.read_item(
                item=app_id, partition_key=app_id,
            )
            return AppRegistrationProfile.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_app_registrations(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AppRegistrationProfile], int]:
        count_query = "SELECT VALUE COUNT(1) FROM c"
        count_results: list[int] = [
            item async for item in self._app_registrations.query_items(
                query=count_query, parameters=[],
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = "SELECT * FROM c ORDER BY c.display_name OFFSET @offset LIMIT @limit"
        data_params: list[dict[str, Any]] = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[AppRegistrationProfile] = [
            AppRegistrationProfile.model_validate(item)
            async for item in self._app_registrations.query_items(
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # MFA record operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_mfa_record(self, record: MfaRegistrationRecord) -> MfaRegistrationRecord:
        body = record.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._mfa_records.upsert_item(body=body)
            return MfaRegistrationRecord.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_mfa_record failed for %s: %s", record.id, exc.message)
            raise

    async def get_mfa_record(self, record_id: str) -> MfaRegistrationRecord | None:
        try:
            item: dict[str, Any] = await self._mfa_records.read_item(
                item=record_id, partition_key=record_id,
            )
            return MfaRegistrationRecord.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_mfa_records(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[MfaRegistrationRecord], int]:
        count_query = "SELECT VALUE COUNT(1) FROM c"
        count_results: list[int] = [
            item async for item in self._mfa_records.query_items(
                query=count_query, parameters=[],
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = "SELECT * FROM c ORDER BY c.id OFFSET @offset LIMIT @limit"
        data_params: list[dict[str, Any]] = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[MfaRegistrationRecord] = [
            MfaRegistrationRecord.model_validate(item)
            async for item in self._mfa_records.query_items(
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Conditional access policy operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_ca_policy(
        self, policy: ConditionalAccessPolicyRecord,
    ) -> ConditionalAccessPolicyRecord:
        body = policy.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._ca_policies.upsert_item(body=body)
            return ConditionalAccessPolicyRecord.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_ca_policy failed for %s: %s", policy.id, exc.message)
            raise

    async def list_ca_policies(self) -> list[ConditionalAccessPolicyRecord]:
        query = "SELECT * FROM c"
        return [
            ConditionalAccessPolicyRecord.model_validate(item)
            async for item in self._ca_policies.query_items(query=query, parameters=[])
        ]

    # ------------------------------------------------------------------
    # Risk detection operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_risk_detection(self, detection: dict[str, Any]) -> None:
        try:
            await self._risk_detections.upsert_item(body=detection)
        except CosmosHttpResponseError as exc:
            logger.error(
                "upsert_risk_detection failed for %s: %s",
                detection.get("id", "unknown"), exc.message,
            )
            raise

    async def list_risk_detections(self, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT * FROM c ORDER BY c._ts DESC OFFSET 0 LIMIT @limit"
        parameters: list[dict[str, Any]] = [{"name": "@limit", "value": limit}]
        return [
            item async for item in self._risk_detections.query_items(
                query=query, parameters=parameters,
            )
        ]

    # ------------------------------------------------------------------
    # Group operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_group(self, group: GroupProfile) -> GroupProfile:
        body = group.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._groups.upsert_item(body=body)
            return GroupProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_group failed for %s: %s", group.id, exc.message)
            raise

    async def get_group(self, group_id: str) -> GroupProfile | None:
        try:
            item: dict[str, Any] = await self._groups.read_item(
                item=group_id, partition_key=group_id,
            )
            return GroupProfile.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def list_groups(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[GroupProfile], int]:
        count_query = "SELECT VALUE COUNT(1) FROM c"
        count_results: list[int] = [
            item async for item in self._groups.query_items(
                query=count_query, parameters=[],
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = "SELECT * FROM c ORDER BY c.display_name OFFSET @offset LIMIT @limit"
        data_params: list[dict[str, Any]] = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[GroupProfile] = [
            GroupProfile.model_validate(item)
            async for item in self._groups.query_items(
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Access review operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_access_review(self, review: AccessReviewDefinition) -> AccessReviewDefinition:
        body = review.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._access_reviews.upsert_item(body=body)
            return AccessReviewDefinition.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_access_review failed for %s: %s", review.id, exc.message)
            raise

    async def list_access_reviews(self) -> list[AccessReviewDefinition]:
        query = "SELECT * FROM c"
        return [
            AccessReviewDefinition.model_validate(item)
            async for item in self._access_reviews.query_items(query=query, parameters=[])
        ]

    # ------------------------------------------------------------------
    # SoD rule operations (PK: /id)
    # ------------------------------------------------------------------

    async def get_sod_rules(self) -> list[SodConflictRule]:
        query = "SELECT * FROM c"
        return [
            SodConflictRule.model_validate(item)
            async for item in self._sod_rules.query_items(query=query, parameters=[])
        ]

    async def upsert_sod_rule(self, rule: SodConflictRule) -> SodConflictRule:
        body = rule.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._sod_rules.upsert_item(body=body)
            return SodConflictRule.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_sod_rule failed for %s: %s", rule.id, exc.message)
            raise

    async def delete_sod_rule(self, rule_id: str) -> None:
        try:
            await self._sod_rules.delete_item(item=rule_id, partition_key=rule_id)
        except CosmosResourceNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Custom role operations (PK: /id)
    # ------------------------------------------------------------------

    async def upsert_custom_role(self, role: CustomRoleProfile) -> CustomRoleProfile:
        body = role.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._custom_roles.upsert_item(body=body)
            return CustomRoleProfile.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_custom_role failed for %s: %s", role.id, exc.message)
            raise

    async def list_custom_roles(self) -> list[CustomRoleProfile]:
        query = "SELECT * FROM c"
        return [
            CustomRoleProfile.model_validate(item)
            async for item in self._custom_roles.query_items(query=query, parameters=[])
        ]

    # ------------------------------------------------------------------
    # Remediation action operations (PK: /id)
    # ------------------------------------------------------------------

    async def create_remediation_action(self, action: RemediationAction) -> RemediationAction:
        body = action.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._remediation_actions.upsert_item(body=body)
            return RemediationAction.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("create_remediation_action failed for %s: %s", action.id, exc.message)
            raise

    async def get_remediation_action(self, action_id: str) -> RemediationAction | None:
        try:
            item: dict[str, Any] = await self._remediation_actions.read_item(
                item=action_id, partition_key=action_id,
            )
            return RemediationAction.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_remediation_action(self, action: RemediationAction) -> RemediationAction:
        return await self.create_remediation_action(action)

    async def update_remediation_status(self, action: RemediationAction) -> RemediationAction:
        body = action.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._remediation_actions.upsert_item(body=body)
            return RemediationAction.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("update_remediation_status failed for %s: %s", action.id, exc.message)
            raise

    async def list_remediation_actions(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[RemediationAction], int]:
        count_query = "SELECT VALUE COUNT(1) FROM c"
        count_results: list[int] = [
            item async for item in self._remediation_actions.query_items(
                query=count_query, parameters=[],
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = "SELECT * FROM c ORDER BY c._ts DESC OFFSET @offset LIMIT @limit"
        data_params: list[dict[str, Any]] = [
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        items: list[RemediationAction] = [
            RemediationAction.model_validate(item)
            async for item in self._remediation_actions.query_items(
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # PIM Session operations (PK: /identity_id)
    # ------------------------------------------------------------------

    async def upsert_pim_session(self, session: PimSession) -> PimSession:
        body = session.model_dump(mode="json")
        result = await self._tracked_upsert(
            self._pim_sessions, body, "upsert_pim_session",
        )
        return PimSession.model_validate(result)

    async def get_pim_session(self, session_id: str) -> PimSession | None:
        query = "SELECT * FROM c WHERE c.id = @id"
        params: list[dict[str, str]] = [{"name": "@id", "value": session_id}]
        items: list[PimSession] = [
            PimSession.model_validate(item)
            async for item in self._pim_sessions.query_items(
                query=query, parameters=params,
            )
        ]
        return items[0] if items else None

    async def list_pim_sessions(
        self,
        status: str | None = None,
        principal_id: str | None = None,
        role_name: str | None = None,
        has_anomalies: bool | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PimSession], int]:
        conditions: list[str] = []
        params: list[dict[str, Any]] = []

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

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        count_query = f"SELECT VALUE COUNT(1) FROM c{where}"
        count_results: list[int] = [
            item async for item in self._pim_sessions.query_items(
                query=count_query, parameters=params,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c{where} "
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
                query=data_query, parameters=data_params,
            )
        ]
        return items, total

    async def get_active_pim_sessions(self) -> list[PimSession]:
        query = "SELECT * FROM c WHERE c.status = 'active' ORDER BY c.activation_time DESC"
        return [
            PimSession.model_validate(item)
            async for item in self._pim_sessions.query_items(query=query, parameters=[])
        ]

    async def get_pim_sessions_for_identity(
        self,
        identity_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[PimSession], int]:
        base_where = "c.identity_id = @identityId"
        params: list[dict[str, str]] = [{"name": "@identityId", "value": identity_id}]

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {base_where}"
        count_results: list[int] = [
            item async for item in self._pim_sessions.query_items(
                query=count_query, parameters=params,
                partition_key=identity_id,
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
                query=data_query, parameters=data_params,
                partition_key=identity_id,
            )
        ]
        return items, total

    async def get_pim_session_analytics(self, days: int = 30) -> dict[str, Any]:
        now = datetime.now(UTC)
        cutoff = (now - timedelta(days=days)).isoformat()
        params: list[dict[str, Any]] = [{"name": "@cutoff", "value": cutoff}]

        # Run server-side aggregations concurrently instead of loading all sessions
        (
            pim_total,
            pim_active,
            pim_expired,
            pim_with_anomalies,
            avg_duration_scalar,
            roles_by_count,
            activators_by_count,
            daily_counts,
        ) = await asyncio.gather(
            self._query_scalar(
                self._pim_sessions,
                "SELECT VALUE COUNT(1) FROM c WHERE c.activation_time >= @cutoff",
                params,
            ),
            self._query_scalar(
                self._pim_sessions,
                "SELECT VALUE COUNT(1) FROM c WHERE c.activation_time >= @cutoff AND c.status = 'active'",
                params,
            ),
            self._query_scalar(
                self._pim_sessions,
                "SELECT VALUE COUNT(1) FROM c WHERE c.activation_time >= @cutoff AND c.status = 'expired'",
                params,
            ),
            self._query_scalar(
                self._pim_sessions,
                "SELECT VALUE COUNT(1) FROM c WHERE c.activation_time >= @cutoff AND ARRAY_LENGTH(c.anomalies) > 0",
                params,
            ),
            self._query_scalar(
                self._pim_sessions,
                "SELECT VALUE AVG(c.duration_minutes) FROM c "
                "WHERE c.activation_time >= @cutoff",
                params,
            ),
            self._tracked_query(
                self._pim_sessions,
                "SELECT VALUE {role_name: c.role_name, cnt: COUNT(1)} FROM c "
                "WHERE c.activation_time >= @cutoff GROUP BY c.role_name",
                params, "pim_analytics.roles",
            ),
            self._tracked_query(
                self._pim_sessions,
                "SELECT VALUE {principal_display_name: c.principal_display_name, cnt: COUNT(1)} FROM c "
                "WHERE c.activation_time >= @cutoff GROUP BY c.principal_display_name",
                params, "pim_analytics.activators",
            ),
            self._query_trend(
                self._pim_sessions,
                "SELECT VALUE {date: SUBSTRING(c.activation_time, 0, 10), cnt: COUNT(1)} "
                "FROM c WHERE c.activation_time >= @cutoff "
                "GROUP BY SUBSTRING(c.activation_time, 0, 10)",
                params,
            ),
        )

        counts = {
            "total": pim_total or 0,
            "active": pim_active or 0,
            "expired": pim_expired or 0,
            "with_anomalies": pim_with_anomalies or 0,
        }
        avg_duration = avg_duration_scalar or 0.0

        roles_by_count.sort(key=lambda x: x.get("cnt", 0), reverse=True)
        activators_by_count.sort(key=lambda x: x.get("cnt", 0), reverse=True)

        # Hour-of-day and anomaly breakdowns still need row-level data,
        # but we only fetch the two small fields needed
        hour_counter: Counter[int] = Counter()
        anomaly_type_counter: Counter[str] = Counter()
        slim_query = (
            "SELECT c.activation_time, c.anomalies FROM c "
            "WHERE c.activation_time >= @cutoff"
        )
        async for item in self._pim_sessions.query_items(
            query=slim_query, parameters=params,
        ):
            act_time = item.get("activation_time", "")
            if isinstance(act_time, str) and len(act_time) >= 13:
                try:
                    dt = datetime.fromisoformat(act_time.replace("Z", "+00:00"))
                    hour_counter[dt.hour] += 1
                except (ValueError, TypeError):
                    pass
            for a in item.get("anomalies", []):
                anomaly_type_counter[a.get("anomaly_type", "unknown")] += 1

        return {
            "total_sessions": counts.get("total", 0),
            "active_sessions": counts.get("active", 0),
            "expired_sessions": counts.get("expired", 0),
            "sessions_with_anomalies": counts.get("with_anomalies", 0),
            "avg_session_duration_minutes": round(avg_duration, 1),
            "top_activated_roles": [
                {"role_name": r.get("role_name", "Unknown"), "count": r.get("cnt", 0)}
                for r in roles_by_count[:10]
            ],
            "top_activators": [
                {"principal_display_name": r.get("principal_display_name", "Unknown"), "count": r.get("cnt", 0)}
                for r in activators_by_count[:10]
            ],
            "activations_by_hour": dict(hour_counter),
            "activations_by_day": [
                {"date": d["date"], "count": int(d["value"])}
                for d in sorted(daily_counts, key=lambda x: x["date"])
            ],
            "anomaly_counts_by_type": dict(anomaly_type_counter),
            "computed_at": now.isoformat(),
        }

    async def get_session_action_events(
        self,
        identity_id: str,
        start: datetime,
        end: datetime,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ActionEvent], int]:
        where = (
            "c.identity_id = @identityId "
            "AND c.timestamp >= @start AND c.timestamp <= @end"
        )
        params: list[dict[str, Any]] = [
            {"name": "@identityId", "value": identity_id},
            {"name": "@start", "value": start.isoformat()},
            {"name": "@end", "value": end.isoformat()},
        ]

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        count_results: list[int] = [
            item async for item in self._action_events.query_items(
                query=count_query, parameters=params,
                partition_key=identity_id,
            )
        ]
        total = count_results[0] if count_results else 0

        data_query = (
            f"SELECT * FROM c WHERE {where} ORDER BY c.timestamp ASC "
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
                query=data_query, parameters=data_params,
                partition_key=identity_id,
            )
        ]
        return items, total

    # ------------------------------------------------------------------
    # Generic count query
    # ------------------------------------------------------------------

    async def count_items(self, container_name: str) -> int:
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

        query = "SELECT VALUE COUNT(1) FROM c"
        results: list[int] = [
            item async for item in container.query_items(query=query, parameters=[])
        ]
        return results[0] if results else 0

    # ------------------------------------------------------------------
    # Dashboard aggregation helpers
    # ------------------------------------------------------------------

    async def _query_to_dict(
        self,
        container: ContainerProxy,
        query: str,
        parameters: list[dict[str, Any]],
        key_field: str,
        value_field: str = "cnt",
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        async for item in container.query_items(query=query, parameters=parameters):
            result[item.get(key_field, "unknown")] = item.get(value_field, 0)
        return result

    async def _query_scalar(
        self,
        container: ContainerProxy,
        query: str,
        parameters: list[dict[str, Any]],
    ) -> Any:
        results: list[Any] = [
            item async for item in container.query_items(query=query, parameters=parameters)
        ]
        return results[0] if results else None

    async def get_dashboard_summary(self) -> dict[str, Any]:
        (
            total_identities,
            total_actions,
            identities_by_type,
            avg_risk_scalar,
            high_risk_count_scalar,
            drift_alerts_open,
            drift_alerts_by_severity,
            bp_total,
            bp_resolved,
            top_risky,
            rec_count_scalar,
            rec_avg_reduction_scalar,
        ) = await asyncio.gather(
            self.count_items("identity_profiles"),
            self.count_items("action_events"),
            self._query_to_dict(
                self._identity_profiles,
                "SELECT VALUE {identity_type: c.identity_type, cnt: COUNT(1)} FROM c GROUP BY c.identity_type",
                [], "identity_type",
            ),
            self._query_scalar(
                self._identity_profiles,
                "SELECT VALUE AVG(c.risk_score) FROM c",
                [],
            ),
            self._query_scalar(
                self._identity_profiles,
                "SELECT VALUE COUNT(1) FROM c WHERE c.risk_score > 70",
                [],
            ),
            self._query_scalar(
                self._drift_alerts,
                "SELECT VALUE COUNT(1) FROM c WHERE c.status = 'open'",
                [],
            ),
            self._query_to_dict(
                self._drift_alerts,
                "SELECT VALUE {severity: c.severity, cnt: COUNT(1)} FROM c "
                "WHERE c.status = 'open' GROUP BY c.severity",
                [], "severity",
            ),
            self.count_items("best_practice_violations"),
            self._query_scalar(
                self._best_practice_violations,
                "SELECT VALUE COUNT(1) FROM c WHERE c.resolved = true",
                [],
            ),
            self._tracked_query(
                self._identity_profiles,
                "SELECT c.id, c.display_name, c.identity_type, c.risk_score FROM c "
                "ORDER BY c.risk_score DESC OFFSET 0 LIMIT 10",
                [], "dashboard.top_risky",
            ),
            self._query_scalar(
                self._role_recommendations,
                "SELECT VALUE COUNT(1) FROM c",
                [],
            ),
            self._query_scalar(
                self._role_recommendations,
                "SELECT VALUE AVG(c.reduction_score) FROM c",
                [],
            ),
        )

        avg_risk = avg_risk_scalar or 0.0
        high_risk_count = high_risk_count_scalar or 0
        bp_resolved_count = bp_resolved or 0
        compliance_score = (bp_resolved_count / bp_total * 100.0) if bp_total > 0 else 100.0
        recommendations_count = rec_count_scalar or 0
        avg_reduction_score = rec_avg_reduction_scalar or 0.0

        return {
            "total_identities": total_identities,
            "total_actions": total_actions,
            "identities_by_type": identities_by_type,
            "avg_risk_score": avg_risk,
            "high_risk_count": high_risk_count,
            "drift_alerts_open": drift_alerts_open or 0,
            "drift_alerts_by_severity": drift_alerts_by_severity,
            "compliance_score": compliance_score,
            "top_risky_identities": top_risky,
            "recommendations_count": recommendations_count,
            "avg_reduction_score": avg_reduction_score,
        }

    async def _query_trend(
        self,
        container: ContainerProxy,
        query: str,
        parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        trend: list[dict[str, Any]] = []
        async for item in container.query_items(query=query, parameters=parameters):
            trend.append({
                "date": item.get("date", ""),
                "value": float(item.get("cnt", 0)),
            })
        return trend

    async def get_trends(self, days: int = 30) -> dict[str, Any]:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        cutoff_params: list[dict[str, Any]] = [{"name": "@cutoff", "value": cutoff}]

        actions_trend, drift_alerts_trend = await asyncio.gather(
            self._query_trend(
                self._action_events,
                "SELECT VALUE {date: SUBSTRING(c.timestamp, 0, 10), cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff "
                "GROUP BY SUBSTRING(c.timestamp, 0, 10)",
                cutoff_params,
            ),
            self._query_trend(
                self._drift_alerts,
                "SELECT VALUE {date: SUBSTRING(c.detected_at, 0, 10), cnt: COUNT(1)} "
                "FROM c WHERE c.detected_at >= @cutoff "
                "GROUP BY SUBSTRING(c.detected_at, 0, 10)",
                cutoff_params,
            ),
        )

        return {
            "risk_score_trend": [],
            "drift_alerts_trend": drift_alerts_trend,
            "actions_trend": actions_trend,
        }

    # ------------------------------------------------------------------
    # Analytics aggregation helpers
    # ------------------------------------------------------------------

    async def _compute_roles_breakdown(self) -> tuple[list[dict[str, Any]], int, int]:
        roles_query = "SELECT c.current_roles FROM c"
        role_counter: Counter[str] = Counter()
        permanent_count = 0
        pim_count = 0
        async for item in self._identity_profiles.query_items(
            query=roles_query, parameters=[],
        ):
            for role in item.get("current_roles", []):
                role_counter[role.get("role_name", "Unknown")] += 1
                if role.get("is_permanent", True):
                    permanent_count += 1
                else:
                    pim_count += 1
        top_roles = [
            {"role_name": name, "count": cnt} for name, cnt in role_counter.most_common(10)
        ]
        return top_roles, permanent_count, pim_count

    async def _compute_permission_utilization(self) -> tuple[int, int]:
        perm_query = "SELECT c.permission_gaps FROM c"
        used_count = 0
        unused_count = 0
        async for item in self._role_recommendations.query_items(
            query=perm_query, parameters=[],
        ):
            for gap in item.get("permission_gaps", []):
                if gap.get("is_used", False):
                    used_count += 1
                else:
                    unused_count += 1
        return used_count, unused_count

    async def _compute_stale_counts(self, now: datetime) -> dict[str, int]:
        async def _stale_at(label: str, threshold_days: int) -> tuple[str, int]:
            threshold = (now - timedelta(days=threshold_days)).isoformat()
            result = await self._query_scalar(
                self._identity_profiles,
                "SELECT VALUE COUNT(1) FROM c WHERE c.last_seen < @threshold",
                [{"name": "@threshold", "value": threshold}],
            )
            return label, result or 0

        results = await asyncio.gather(
            _stale_at("30d", 30),
            _stale_at("60d", 60),
            _stale_at("90d", 90),
        )
        return dict(results)

    async def get_analytics_data(self, days: int = 30) -> dict[str, Any]:
        now = datetime.now(UTC)
        cutoff = (now - timedelta(days=days)).isoformat()
        base_params: list[dict[str, Any]] = [{"name": "@cutoff", "value": cutoff}]

        # Fire all independent queries concurrently
        (
            total_actions_period,
            failure_count_scalar,
            unique_active_scalar,
            daily_action_counts,
            top_actions_raw,
            active_raw,
            actions_by_source,
            success_vs_failure,
            resource_raw,
            roles_breakdown,
            stale_counts,
            new_identities_scalar,
            perm_utilization,
            overprivileged_scalar,
            violations_by_type,
            credential_expiry,
            recent_drift,
        ) = await asyncio.gather(
            self._query_scalar(
                self._action_events,
                "SELECT VALUE COUNT(1) FROM c WHERE c.timestamp >= @cutoff",
                base_params,
            ),
            self._query_scalar(
                self._action_events,
                "SELECT VALUE COUNT(1) FROM c WHERE c.timestamp >= @cutoff AND c.result = 'failure'",
                base_params,
            ),
            self._query_scalar(
                self._action_events,
                "SELECT VALUE COUNT(1) FROM "
                "(SELECT DISTINCT c.identity_id FROM c WHERE c.timestamp >= @cutoff)",
                base_params,
            ),
            self._query_trend(
                self._action_events,
                "SELECT VALUE {date: SUBSTRING(c.timestamp, 0, 10), cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff "
                "GROUP BY SUBSTRING(c.timestamp, 0, 10)",
                base_params,
            ),
            self._tracked_query(
                self._action_events,
                "SELECT VALUE {action: c.action, cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff GROUP BY c.action",
                base_params, "analytics.top_actions",
            ),
            self._tracked_query(
                self._action_events,
                "SELECT VALUE {identity_id: c.identity_id, identity_display_name: c.identity_display_name, cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff "
                "GROUP BY c.identity_id, c.identity_display_name",
                base_params, "analytics.active_identities",
            ),
            self._query_to_dict(
                self._action_events,
                "SELECT VALUE {source: c.source, cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff GROUP BY c.source",
                base_params, "source",
            ),
            self._query_to_dict(
                self._action_events,
                "SELECT VALUE {result: c.result, cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff GROUP BY c.result",
                base_params, "result",
            ),
            self._tracked_query(
                self._action_events,
                "SELECT VALUE {resource: c.resource, resource_type: c.resource_type, cnt: COUNT(1)} "
                "FROM c WHERE c.timestamp >= @cutoff AND c.resource != null "
                "GROUP BY c.resource, c.resource_type",
                base_params, "analytics.top_resources",
            ),
            self._compute_roles_breakdown(),
            self._compute_stale_counts(now),
            self._query_scalar(
                self._identity_profiles,
                "SELECT VALUE COUNT(1) FROM c WHERE c.first_seen >= @cutoff",
                base_params,
            ),
            self._compute_permission_utilization(),
            self._query_scalar(
                self._role_recommendations,
                "SELECT VALUE COUNT(1) FROM c WHERE c.reduction_score > 30",
                [],
            ),
            self._query_to_dict(
                self._best_practice_violations,
                "SELECT VALUE {violation_type: c.violation_type, cnt: COUNT(1)} FROM c "
                "WHERE c.resolved = false GROUP BY c.violation_type",
                [], "violation_type",
            ),
            self._tracked_query(
                self._best_practice_violations,
                "SELECT c.identity_id, c.identity_display_name, c.detected_at FROM c "
                "WHERE c.violation_type = 'sp_credential_expiry' AND c.resolved = false "
                "ORDER BY c.detected_at DESC OFFSET 0 LIMIT 10",
                [], "analytics.cred_expiry",
            ),
            self._tracked_query(
                self._drift_alerts,
                "SELECT * FROM c ORDER BY c.detected_at DESC OFFSET 0 LIMIT 5",
                [], "analytics.recent_drift",
            ),
        )

        # Unpack aggregated results
        total_actions = total_actions_period or 0
        failures = failure_count_scalar or 0
        failed_action_pct = (failures / total_actions * 100.0) if total_actions > 0 else 0.0
        unique_active = unique_active_scalar or 0
        avg_actions = (total_actions / unique_active) if unique_active > 0 else 0.0
        new_identities_count = new_identities_scalar or 0
        overprivileged_count = overprivileged_scalar or 0
        top_roles, permanent_count, pim_count = roles_breakdown
        used_count, unused_count = perm_utilization

        daily_action_counts.sort(key=lambda x: x["date"])

        top_actions_raw.sort(key=lambda x: x.get("cnt", 0), reverse=True)
        top_actions = [
            {"action": r.get("action", ""), "count": r.get("cnt", 0)}
            for r in top_actions_raw[:10]
        ]

        active_raw.sort(key=lambda x: x.get("cnt", 0), reverse=True)
        most_active = [
            {
                "identity_id": r.get("identity_id", ""),
                "display_name": r.get("identity_display_name", ""),
                "identity_type": r.get("identity_id", "").split("_")[0]
                if "_" in r.get("identity_id", "") else "User",
                "count": r.get("cnt", 0),
            }
            for r in active_raw[:10]
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

        cred_expiry_list = [
            {
                "identity_id": item.get("identity_id", ""),
                "identity_display_name": item.get("identity_display_name", ""),
                "detected_at": item.get("detected_at", ""),
            }
            for item in credential_expiry
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
            "credential_expiry_violations": cred_expiry_list,
            "recent_drift_alerts": recent_drift,
        }

    # ------------------------------------------------------------------
    # Access Path Analyses (PK: /identity_id)
    # ------------------------------------------------------------------

    async def upsert_access_path_analysis(
        self, analysis: AccessPathAnalysis,
    ) -> AccessPathAnalysis:
        body = analysis.model_dump(mode="json")
        try:
            result: dict[str, Any] = await self._access_path_analyses.upsert_item(body=body)
            return AccessPathAnalysis.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("upsert_access_path_analysis failed for %s: %s", analysis.id, exc)
            raise

    async def get_access_path_analysis_by_identity(
        self, identity_id: str,
    ) -> AccessPathAnalysis | None:
        query = "SELECT * FROM c WHERE c.identity_id = @iid"
        params: list[dict[str, str]] = [{"name": "@iid", "value": identity_id}]
        items: list[AccessPathAnalysis] = [
            AccessPathAnalysis.model_validate(item)
            async for item in self._access_path_analyses.query_items(
                query=query, parameters=params,
                partition_key=identity_id,
            )
        ]
        return items[0] if items else None

    async def list_access_path_analyses(
        self,
        min_risk: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AccessPathAnalysis], int]:
        where = "c.total_paths > 0"

        if min_risk:
            risk_order = {"critical": 1, "high": 2, "medium": 3}
            allowed = [k for k, v in risk_order.items() if v <= risk_order.get(min_risk, 3)]
            placeholders = ", ".join(f"'{r}'" for r in allowed)
            where += f" AND c.highest_risk IN ({placeholders})"

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        count_results: list[int] = [
            item async for item in self._access_path_analyses.query_items(
                query=count_query, parameters=[],
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
                query=query, parameters=[],
            )
        ]
        return items, total

    async def get_access_path_summary(self) -> AccessPathSummary:
        total_q, critical_q, high_q, medium_q = await asyncio.gather(
            self._query_scalar(
                self._access_path_analyses,
                "SELECT VALUE COUNT(1) FROM c WHERE c.total_paths > 0", [],
            ),
            self._query_scalar(
                self._access_path_analyses,
                "SELECT VALUE COUNT(1) FROM c WHERE c.total_paths > 0 AND c.highest_risk = 'critical'", [],
            ),
            self._query_scalar(
                self._access_path_analyses,
                "SELECT VALUE COUNT(1) FROM c WHERE c.total_paths > 0 AND c.highest_risk = 'high'", [],
            ),
            self._query_scalar(
                self._access_path_analyses,
                "SELECT VALUE COUNT(1) FROM c WHERE c.total_paths > 0 AND c.highest_risk = 'medium'", [],
            ),
        )
        return AccessPathSummary(
            total_identities_with_paths=total_q or 0,
            critical_count=critical_q or 0,
            high_count=high_q or 0,
            medium_count=medium_q or 0,
        )

    # ------------------------------------------------------------------
    # Scan event log operations (PK: /scanId)
    # ------------------------------------------------------------------

    async def append_scan_log(self, entry: ScanLogEntry) -> None:
        body = entry.model_dump(mode="json")
        body["scanId"] = entry.scan_id
        try:
            await self._scan_events.upsert_item(body=body)
        except CosmosHttpResponseError as exc:
            logger.warning("append_scan_log failed for %s: %s", entry.id, exc.message)

    async def get_scan_logs(
        self,
        scan_id: str,
        offset: int = 0,
        limit: int = 200,
        level: str | None = None,
        phase: str | None = None,
    ) -> tuple[list[ScanLogEntry], int]:
        filters = ["c.scanId = @scanId"]
        params: list[dict[str, str]] = [{"name": "@scanId", "value": scan_id}]
        if level:
            filters.append("c.level = @level")
            params.append({"name": "@level", "value": level})
        if phase:
            filters.append("c.phase = @phase")
            params.append({"name": "@phase", "value": phase})
        where = " AND ".join(filters)

        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where}"
        count_results: list[int] = [
            item async for item in self._scan_events.query_items(
                query=count_query, parameters=params,
                partition_key=scan_id,
            )
        ]
        total = count_results[0] if count_results else 0

        query = (
            f"SELECT * FROM c WHERE {where} ORDER BY c.timestamp ASC "
            f"OFFSET {offset} LIMIT {limit}"
        )
        items: list[ScanLogEntry] = [
            ScanLogEntry.model_validate(item)
            async for item in self._scan_events.query_items(
                query=query, parameters=params,
                partition_key=scan_id,
            )
        ]
        return items, total

    async def get_scan_events_after(
        self,
        scan_id: str,
        after_timestamp: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        filters = ["c.scanId = @scanId"]
        params: list[dict[str, str]] = [{"name": "@scanId", "value": scan_id}]
        if after_timestamp:
            filters.append("c.timestamp > @after")
            params.append({"name": "@after", "value": after_timestamp})
        where = " AND ".join(filters)
        query = (
            f"SELECT * FROM c WHERE {where} ORDER BY c.timestamp ASC OFFSET 0 LIMIT {limit}"
        )
        try:
            return [
                item async for item in self._scan_events.query_items(
                    query=query, parameters=params,
                    partition_key=scan_id,
                )
            ]
        except CosmosHttpResponseError as exc:
            logger.warning("get_scan_events_after failed for scan %s: %s", scan_id, exc.message)
            return []
