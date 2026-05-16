# backend/app/services/project_repo_cache.py
from __future__ import annotations

from azure.cosmos.aio import CosmosClient

from app.services.project_repo import ProjectRepo


class ProjectRepoCache:
    """Caches ProjectRepo instances per project database."""

    def __init__(self, client: CosmosClient) -> None:
        self._client = client
        self._cache: dict[str, ProjectRepo] = {}

    async def get_repo(self, database_name: str) -> ProjectRepo:
        """Get or create a ProjectRepo for the given database."""
        if database_name not in self._cache:
            db = self._client.get_database_client(database_name)
            self._cache[database_name] = await ProjectRepo.create(db)
        return self._cache[database_name]

    def evict(self, database_name: str) -> None:
        """Remove a cached ProjectRepo (e.g., after project deletion)."""
        self._cache.pop(database_name, None)
