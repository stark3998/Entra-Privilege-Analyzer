from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from azure.core import MatchConditions
from azure.cosmos import PartitionKey
from azure.cosmos.aio import ContainerProxy, CosmosClient, DatabaseProxy
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError

from app.config import Settings
from app.models.alert_rules import AlertRule, ScanSchedule
from app.models.project import Project, ProjectMember, ScanLogEntry, ScanRecord
from app.observability import cosmos_ru_counter, get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

_repo: MasterRepo | None = None

_PROJECT_LEASE_RELEASE_RETRIES = 3


def _parse_cosmos_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


class MasterRepo:
    """Repository for master database operations (projects, members, scans, schedules, alerts)."""

    def __init__(
        self,
        client: CosmosClient,
        db: DatabaseProxy,
        projects: ContainerProxy,
        project_members: ContainerProxy,
        scan_history: ContainerProxy,
        scan_schedules: ContainerProxy,
        alert_rules: ContainerProxy,
    ) -> None:
        self._client = client
        self._db = db
        self._projects = projects
        self._project_members = project_members
        self._scan_history = scan_history
        self._scan_schedules = scan_schedules
        self._alert_rules = alert_rules

    @classmethod
    async def create(cls, client: CosmosClient, settings: Settings) -> MasterRepo:
        """Initialise the master database and its containers."""
        db = await client.create_database_if_not_exists(id=settings.cosmos_master_database)

        projects = await db.create_container_if_not_exists(
            id="projects", partition_key=PartitionKey(path="/ownerId"),
        )
        project_members = await db.create_container_if_not_exists(
            id="project_members", partition_key=PartitionKey(path="/projectId"),
        )
        scan_history = await db.create_container_if_not_exists(
            id="scan_history", partition_key=PartitionKey(path="/projectId"),
        )
        scan_schedules = await db.create_container_if_not_exists(
            id="scan_schedules", partition_key=PartitionKey(path="/projectId"),
        )
        alert_rules = await db.create_container_if_not_exists(
            id="alert_rules", partition_key=PartitionKey(path="/projectId"),
        )

        logger.info(
            "Master DB initialised — database=%s, containers="
            "projects,project_members,scan_history,scan_schedules,alert_rules",
            settings.cosmos_master_database,
        )
        return cls(
            client=client,
            db=db,
            projects=projects,
            project_members=project_members,
            scan_history=scan_history,
            scan_schedules=scan_schedules,
            alert_rules=alert_rules,
        )

    # ------------------------------------------------------------------
    # Internal helpers for logging + RU tracking
    # ------------------------------------------------------------------

    def _log_op(
        self,
        op: str,
        container: str,
        *,
        items: int = 1,
        duration_ms: float | None = None,
        ru: float | None = None,
    ) -> None:
        extra = ""
        if duration_ms is not None:
            extra += f" duration={duration_ms:.0f}ms"
        if ru is not None:
            extra += f" ru={ru:.2f}"
        if items > 1:
            extra += f" items={items}"
        logger.debug("MasterRepo.%s [%s]%s", op, container, extra)

    async def _tracked_upsert(
        self,
        container: ContainerProxy,
        body: dict[str, Any],
        op_name: str,
    ) -> dict[str, Any]:
        with tracer.start_as_current_span(
            "cosmos.upsert",
            attributes={"db.system": "cosmosdb", "db.operation": op_name, "db.cosmosdb.container": container.id},
        ) as span:
            t0 = time.monotonic()
            ru: float = 0.0

            def _hook(headers: dict[str, str], _: Any) -> None:
                nonlocal ru
                ru = float(headers.get("x-ms-request-charge", 0))

            result: dict[str, Any] = await container.upsert_item(
                body=body, response_hook=_hook,
            )
            elapsed = (time.monotonic() - t0) * 1000
            span.set_attribute("db.cosmosdb.request_units", ru)
            span.set_attribute("duration_ms", elapsed)
            if cosmos_ru_counter is not None:
                cosmos_ru_counter.add(ru, attributes={"operation": op_name})
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
        with tracer.start_as_current_span(
            "cosmos.query",
            attributes={"db.system": "cosmosdb", "db.operation": op_name, "db.cosmosdb.container": container.id},
        ) as span:
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
            span.set_attribute("db.cosmosdb.request_units", ru)
            span.set_attribute("db.cosmosdb.items_returned", len(results))
            span.set_attribute("duration_ms", elapsed)
            if cosmos_ru_counter is not None:
                cosmos_ru_counter.add(ru, attributes={"operation": op_name})
            self._log_op(op_name, container.id, items=len(results), duration_ms=elapsed, ru=ru)
            return results

    # ------------------------------------------------------------------
    # Project operations
    # ------------------------------------------------------------------

    async def get_project(self, project_id: str) -> Project | None:
        query = "SELECT * FROM c WHERE c.id = @id"
        params: list[dict[str, str]] = [{"name": "@id", "value": project_id}]
        items: list[Project] = [
            Project.model_validate(item)
            async for item in self._projects.query_items(
                query=query, parameters=params,
            )
        ]
        return items[0] if items else None

    async def _get_project_document(self, project_id: str) -> dict[str, Any] | None:
        query = "SELECT * FROM c WHERE c.id = @id"
        params: list[dict[str, str]] = [{"name": "@id", "value": project_id}]
        items: list[dict[str, Any]] = [
            item
            async for item in self._projects.query_items(
                query=query, parameters=params,
            )
        ]
        return items[0] if items else None

    async def upsert_project(self, project: Project) -> Project:
        body = project.model_dump(mode="json")
        body["ownerId"] = project.owner_id
        try:
            result = await self._tracked_upsert(
                self._projects, body, "upsert_project",
            )
            return Project.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error("Cosmos upsert_project failed for %s: %s", project.id, exc.message)
            raise

    async def list_projects_for_user(
        self, user_id: str, email: str = "",
    ) -> list[Project]:
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

        if member_project_ids:
            member_projects = await asyncio.gather(
                *(self.get_project(pid) for pid in member_project_ids)
            )
            owned.extend(p for p in member_projects if p is not None)

        return owned

    async def delete_project(self, owner_id: str, project_id: str) -> None:
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
    # Project lease operations
    # ------------------------------------------------------------------

    async def try_acquire_project_scan_lease(
        self,
        project_id: str,
        scan_id: str,
        owner_instance_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> Project | None:
        project_doc = await self._get_project_document(project_id)
        if project_doc is None:
            return None

        active_scan_id = project_doc.get("active_scan_id")
        active_lease_expires_at = _parse_cosmos_datetime(
            project_doc.get("active_scan_lease_expires_at")
        )
        if (
            active_scan_id
            and active_scan_id != scan_id
            and active_lease_expires_at is not None
            and active_lease_expires_at > heartbeat_at
        ):
            return None

        project_doc["active_scan_id"] = scan_id
        project_doc["active_scan_owner_instance_id"] = owner_instance_id
        project_doc["active_scan_heartbeat_at"] = heartbeat_at.isoformat()
        project_doc["active_scan_lease_expires_at"] = lease_expires_at.isoformat()

        try:
            result: dict[str, Any] = await self._projects.replace_item(
                item=project_doc["id"],
                body=project_doc,
                etag=project_doc.get("_etag"),
                match_condition=MatchConditions.IfNotModified,
            )
            return Project.model_validate(result)
        except CosmosHttpResponseError as exc:
            if getattr(exc, "status_code", None) in {409, 412}:
                return None
            raise

    async def renew_project_scan_lease(
        self,
        project_id: str,
        scan_id: str,
        owner_instance_id: str,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        project_doc = await self._get_project_document(project_id)
        if project_doc is None:
            return False
        if project_doc.get("active_scan_id") != scan_id:
            return False
        if project_doc.get("active_scan_owner_instance_id") != owner_instance_id:
            return False

        project_doc["active_scan_heartbeat_at"] = heartbeat_at.isoformat()
        project_doc["active_scan_lease_expires_at"] = lease_expires_at.isoformat()
        try:
            await self._projects.replace_item(
                item=project_doc["id"],
                body=project_doc,
                etag=project_doc.get("_etag"),
                match_condition=MatchConditions.IfNotModified,
            )
            return True
        except CosmosHttpResponseError as exc:
            if getattr(exc, "status_code", None) in {409, 412}:
                return False
            raise

    async def has_project_scan_lease(
        self,
        project_id: str,
        scan_id: str,
        owner_instance_id: str,
        as_of: datetime,
    ) -> bool:
        project_doc = await self._get_project_document(project_id)
        if project_doc is None:
            return False
        if project_doc.get("active_scan_id") != scan_id:
            return False
        if project_doc.get("active_scan_owner_instance_id") != owner_instance_id:
            return False
        active_lease_expires_at = _parse_cosmos_datetime(
            project_doc.get("active_scan_lease_expires_at")
        )
        return active_lease_expires_at is not None and active_lease_expires_at > as_of

    async def release_project_scan_lease(
        self,
        project_id: str,
        scan_id: str,
        owner_instance_id: str,
        completed_at: datetime,
        last_scan_status: str,
        *,
        identity_count: int | None = None,
    ) -> Project | None:
        for attempt in range(_PROJECT_LEASE_RELEASE_RETRIES):
            project_doc = await self._get_project_document(project_id)
            if project_doc is None:
                return None
            if project_doc.get("active_scan_id") != scan_id:
                return None
            if project_doc.get("active_scan_owner_instance_id") != owner_instance_id:
                return None

            project_doc["last_scan_at"] = completed_at.isoformat()
            project_doc["last_scan_status"] = last_scan_status
            project_doc["updated_at"] = completed_at.isoformat()
            if identity_count is not None:
                project_doc["identity_count"] = identity_count
            project_doc.pop("active_scan_id", None)
            project_doc.pop("active_scan_owner_instance_id", None)
            project_doc.pop("active_scan_heartbeat_at", None)
            project_doc.pop("active_scan_lease_expires_at", None)

            try:
                result: dict[str, Any] = await self._projects.replace_item(
                    item=project_doc["id"],
                    body=project_doc,
                    etag=project_doc.get("_etag"),
                    match_condition=MatchConditions.IfNotModified,
                )
                return Project.model_validate(result)
            except CosmosHttpResponseError as exc:
                if getattr(exc, "status_code", None) in {409, 412}:
                    if attempt == _PROJECT_LEASE_RELEASE_RETRIES - 1:
                        return None
                    continue
                raise
        return None

    async def clear_project_scan_lease(
        self,
        project_id: str,
        scan_id: str,
        owner_instance_id: str,
    ) -> bool:
        project_doc = await self._get_project_document(project_id)
        if project_doc is None:
            return False
        if project_doc.get("active_scan_id") != scan_id:
            return False
        if project_doc.get("active_scan_owner_instance_id") != owner_instance_id:
            return False

        project_doc.pop("active_scan_id", None)
        project_doc.pop("active_scan_owner_instance_id", None)
        project_doc.pop("active_scan_heartbeat_at", None)
        project_doc.pop("active_scan_lease_expires_at", None)

        try:
            await self._projects.replace_item(
                item=project_doc["id"],
                body=project_doc,
                etag=project_doc.get("_etag"),
                match_condition=MatchConditions.IfNotModified,
            )
            return True
        except CosmosHttpResponseError as exc:
            if getattr(exc, "status_code", None) in {409, 412}:
                return False
            raise

    # ------------------------------------------------------------------
    # Project member operations
    # ------------------------------------------------------------------

    async def get_project_member(
        self, project_id: str, user_id: str,
    ) -> ProjectMember | None:
        query = "SELECT * FROM c WHERE c.projectId = @projectId AND c.user_id = @userId"
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
        query = "SELECT * FROM c WHERE c.projectId = @projectId AND LOWER(c.email) = LOWER(@email)"
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
        query = "SELECT * FROM c WHERE c.projectId = @projectId"
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        return [
            ProjectMember.model_validate(item)
            async for item in self._project_members.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]

    async def delete_project_member(self, project_id: str, member_id: str) -> None:
        try:
            await self._project_members.delete_item(item=member_id, partition_key=project_id)
        except CosmosResourceNotFoundError:
            pass

    async def list_user_memberships(
        self, user_id: str, email: str = "",
    ) -> list[ProjectMember]:
        if email:
            query = "SELECT * FROM c WHERE c.user_id = @userId OR LOWER(c.email) = LOWER(@email)"
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
        try:
            item: dict[str, Any] = await self._scan_history.read_item(
                item=scan_id, partition_key=project_id,
            )
            return ScanRecord.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_scan(self, scan: ScanRecord) -> ScanRecord:
        body = scan.model_dump(mode="json")
        body["projectId"] = scan.project_id
        try:
            result = await self._tracked_upsert(
                self._scan_history, body, "upsert_scan",
            )
            return ScanRecord.model_validate(result)
        except CosmosHttpResponseError as exc:
            logger.error(
                "Cosmos upsert_scan failed for %s/%s: %s",
                scan.project_id, scan.id, exc.message,
            )
            raise

    async def list_scans(
        self, project_id: str, offset: int = 0, limit: int = 20,
    ) -> tuple[list[ScanRecord], int]:
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
    # Scan event log operations
    # ------------------------------------------------------------------

    async def append_scan_log(self, entry: ScanLogEntry) -> None:
        body = entry.model_dump(mode="json")
        body["scanId"] = entry.scan_id
        try:
            await self._scan_history.upsert_item(body=body)
        except CosmosHttpResponseError as exc:
            logger.warning("Cosmos append_scan_log failed for %s: %s", entry.id, exc.message)

    # ------------------------------------------------------------------
    # Scan schedule operations
    # ------------------------------------------------------------------

    async def get_scan_schedules(self) -> list[ScanSchedule]:
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
        query = "SELECT * FROM c WHERE c.projectId = @projectId"
        params: list[dict[str, str]] = [{"name": "@projectId", "value": project_id}]
        return [
            ScanSchedule.model_validate(item)
            async for item in self._scan_schedules.query_items(
                query=query, parameters=params, partition_key=project_id,
            )
        ]

    async def upsert_scan_schedule(self, schedule: ScanSchedule) -> ScanSchedule:
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
        try:
            item: dict[str, Any] = await self._alert_rules.read_item(
                item=rule_id, partition_key=project_id,
            )
            return AlertRule.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_alert_rule(self, rule: AlertRule) -> AlertRule:
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
        try:
            await self._alert_rules.delete_item(
                item=rule_id, partition_key=project_id,
            )
        except CosmosResourceNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.close()


async def init_master_repo(settings: Settings) -> MasterRepo:
    """Create and cache the global MasterRepo singleton."""
    global _repo
    client = CosmosClient(url=settings.cosmos_endpoint, credential=settings.cosmos_key)
    _repo = await MasterRepo.create(client, settings)
    return _repo


def get_master_repo() -> MasterRepo:
    if _repo is None:
        raise RuntimeError("MasterRepo has not been initialised — call init_master_repo() first")
    return _repo
