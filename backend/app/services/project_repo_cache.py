# backend/app/services/project_repo_cache.py
from __future__ import annotations

from collections import OrderedDict

from azure.cosmos.aio import CosmosClient

from app.services.project_repo import ProjectRepo

_DEFAULT_MAX_SIZE = 50


class ProjectRepoCache:
    """LRU cache of ProjectRepo instances per project database."""

    def __init__(self, client: CosmosClient, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        self._client = client
        self._max_size = max_size
        self._cache: OrderedDict[str, ProjectRepo] = OrderedDict()

    async def get_repo(self, database_name: str) -> ProjectRepo:
        """Get or create a ProjectRepo for the given database."""
        if database_name in self._cache:
            self._cache.move_to_end(database_name)
            return self._cache[database_name]

        db = self._client.get_database_client(database_name)
        repo = await ProjectRepo.create(db)
        self._cache[database_name] = repo

        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

        return repo

    def evict(self, database_name: str) -> None:
        """Remove a cached ProjectRepo (e.g., after project deletion)."""
        self._cache.pop(database_name, None)

    def clear(self) -> None:
        """Remove all cached repos."""
        self._cache.clear()
