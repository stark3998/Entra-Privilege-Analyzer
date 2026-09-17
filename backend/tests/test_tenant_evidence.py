from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.models.tenant_evidence import TenantRegistryEntry
from app.services.cosmos_schema import PROJECT_CONTAINERS, TENANT_EVIDENCE_CONTAINERS
from app.services.master_repo import MasterRepo
from app.services.project_db_manager import ProjectDatabaseManager
from app.services.tenant_evidence_db_manager import (
    TenantEvidenceDatabaseManager,
    tenant_evidence_database_name,
)
from app.services.tenant_evidence_repo_cache import TenantEvidenceRepoCache


class FakeDatabase:
    def __init__(self) -> None:
        self.containers: list[dict[str, Any]] = []

    async def create_container_if_not_exists(self, **kwargs: Any) -> None:
        self.containers.append(kwargs)

    def get_container_client(self, name: str) -> str:
        return name


class FakeCosmosClient:
    def __init__(self) -> None:
        self.databases: dict[str, FakeDatabase] = {}
        self.create_calls: list[str] = []

    async def create_database_if_not_exists(self, name: str) -> FakeDatabase:
        self.create_calls.append(name)
        return self.databases.setdefault(name, FakeDatabase())

    def get_database_client(self, name: str) -> FakeDatabase:
        return self.databases.setdefault(name, FakeDatabase())


class FakeTenantRegistry:
    def __init__(self, item: dict[str, Any]) -> None:
        self.item = item

    async def read_item(self, **_kwargs: Any) -> dict[str, Any]:
        return self.item.copy()

    async def replace_item(self, *, body: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        self.item = body.copy()
        return self.item


def test_tenant_database_name_is_stable_and_validated() -> None:
    assert tenant_evidence_database_name(" Tenant-001 ") == "tenant-tenant-001"

    with pytest.raises(ValueError):
        tenant_evidence_database_name("../tenant")


@pytest.mark.asyncio
async def test_provisions_canonical_tenant_evidence_containers() -> None:
    client = FakeCosmosClient()
    manager = TenantEvidenceDatabaseManager(client, raw_activity_ttl=86400)

    database_name = await manager.provision_tenant_database("tenant-001")

    assert database_name == "tenant-tenant-001"
    containers = client.databases[database_name].containers
    assert {container["id"] for container in containers} == {
        definition.name for definition in TENANT_EVIDENCE_CONTAINERS
    }
    activity = next(
        container for container in containers if container["id"] == "activity_events"
    )
    assert activity["default_ttl"] == 86400
    audit_relevant = {
        "identity_nodes",
        "entitlement_edges",
        "evidence_lineage",
        "collection_cursors",
        "data_quality",
    }
    assert audit_relevant.issubset({container["id"] for container in containers})


@pytest.mark.asyncio
async def test_ensure_tenant_database_recreates_missing_database() -> None:
    client = FakeCosmosClient()
    manager = TenantEvidenceDatabaseManager(client, raw_activity_ttl=86400)

    await manager.ensure_tenant_database("tenant-001")

    assert client.create_calls == ["tenant-tenant-001"]
    assert "tenant-tenant-001" in client.databases


@pytest.mark.asyncio
async def test_registering_project_preserves_tenant_governance_state() -> None:
    now = datetime(2026, 9, 15, tzinfo=UTC)
    current = TenantRegistryEntry(
        id="tenant-001",
        database_name="tenant-tenant-001",
        status="active",
        project_ids=["project-001"],
        raw_activity_retention_days=730,
        legal_hold=True,
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")
    current["_etag"] = "etag-1"
    registry = FakeTenantRegistry(current)
    repo = object.__new__(MasterRepo)
    repo._tenant_registry = registry
    incoming = TenantRegistryEntry(
        id="tenant-001",
        database_name="tenant-tenant-001",
        status="provisioning",
        raw_activity_retention_days=365,
        legal_hold=False,
        created_at=now,
        updated_at=now,
    )

    result = await repo.register_tenant_project(incoming, "project-002")

    assert result.project_ids == ["project-001", "project-002"]
    assert result.status == "active"
    assert result.raw_activity_retention_days == 730
    assert result.legal_hold is True


@pytest.mark.asyncio
async def test_repo_cache_shares_tenant_repo_and_evicts_lru() -> None:
    client = FakeCosmosClient()
    cache = TenantEvidenceRepoCache(client, max_size=1)

    first = await cache.get_repo("tenant-001")
    same = await cache.get_repo("tenant-001")
    await cache.get_repo("tenant-002")
    recreated = await cache.get_repo("tenant-001")

    assert same is first
    assert recreated is not first


@pytest.mark.asyncio
async def test_existing_databases_receive_additive_schema_upgrades() -> None:
    client = FakeCosmosClient()
    project_database = await client.create_database_if_not_exists("project-existing")
    tenant_database = await client.create_database_if_not_exists("tenant-existing")

    await ProjectDatabaseManager(client).ensure_project_database("project-existing")
    await TenantEvidenceDatabaseManager(client).ensure_tenant_database("existing")

    assert {item["id"] for item in project_database.containers} == {
        definition.name for definition in PROJECT_CONTAINERS
    }
    assert {item["id"] for item in tenant_database.containers} == {
        definition.name for definition in TENANT_EVIDENCE_CONTAINERS
    }
