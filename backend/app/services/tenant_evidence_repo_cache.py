from __future__ import annotations

from collections import OrderedDict

from azure.cosmos.aio import CosmosClient

from app.services.tenant_evidence_db_manager import (
    TenantEvidenceDatabaseManager,
    tenant_evidence_database_name,
)
from app.services.tenant_evidence_repo import TenantEvidenceRepo

_DEFAULT_MAX_SIZE = 50


class TenantEvidenceRepoCache:
    def __init__(
        self,
        client: CosmosClient,
        max_size: int = _DEFAULT_MAX_SIZE,
        raw_activity_ttl: int = 31536000,
    ) -> None:
        self._client = client
        self._max_size = max_size
        self._raw_activity_ttl = raw_activity_ttl
        self._cache: OrderedDict[str, TenantEvidenceRepo] = OrderedDict()

    async def get_repo(self, tenant_id: str) -> TenantEvidenceRepo:
        database_name = tenant_evidence_database_name(tenant_id)
        if database_name in self._cache:
            self._cache.move_to_end(database_name)
            return self._cache[database_name]
        await TenantEvidenceDatabaseManager(
            self._client,
            self._raw_activity_ttl,
        ).ensure_tenant_database(tenant_id)
        repo = await TenantEvidenceRepo.create(
            self._client.get_database_client(database_name)
        )
        self._cache[database_name] = repo
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return repo

    def evict(self, tenant_id: str) -> None:
        self._cache.pop(tenant_evidence_database_name(tenant_id), None)

    def clear(self) -> None:
        self._cache.clear()
