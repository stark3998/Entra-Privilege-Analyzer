# backend/tests/test_auth.py
from __future__ import annotations

from datetime import datetime

import pytest
from httpx import AsyncClient

from app.auth.deps import _MOCK_USER, validate_project_access
from app.models.project import Project


class _RepoStub:
    def __init__(self, project: Project | None) -> None:
        self._project = project

    async def get_project(self, project_id: str) -> Project | None:
        if self._project is None or self._project.id != project_id:
            return None
        return self._project

    async def list_projects_for_user(self, user_id: str, email: str = "") -> list[Project]:
        if self._project is None or self._project.owner_id != user_id:
            return []
        return [self._project]


@pytest.mark.asyncio
async def test_healthz_returns_ok(client: AsyncClient) -> None:
    """GET /healthz should always return 200."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_tenants_me_local_mode(client: AsyncClient) -> None:
    """In LOCAL_MODE, GET /api/tenants/me should return the mock user."""
    resp = await client.get("/api/projects/me")
    assert resp.status_code == 200

    body = resp.json()
    assert body["tenant_id"] == "c8a8cdf0-9270-446b-9930-3d017bf24220"
    assert body["name"] == "Jatin Madan"
    assert body["email"] == "jatmadan@deloitte.com"
    assert set(body["roles"]) == {"SecurityEngineer", "IAMAdmin", "Executive"}


@pytest.mark.asyncio
async def test_tenants_me_has_all_three_roles(client: AsyncClient) -> None:
    """The mock user in LOCAL_MODE must carry all three app roles."""
    resp = await client.get("/api/projects/me")
    roles = resp.json()["roles"]
    assert len(roles) == 3
    for role in ("SecurityEngineer", "IAMAdmin", "Executive"):
        assert role in roles


@pytest.mark.asyncio
async def test_validate_project_access_local_mode_returns_real_project(settings) -> None:
    """In LOCAL_MODE, a real stored project should win over the mock project."""
    project = Project(
        id="real-project",
        owner_id=_MOCK_USER.oid,
        name="Real Project",
        target_tenant_id="c8a8cdf0-9270-446b-9930-3d017bf24220",
        target_tenant_name="Advisory Cloud Cyber Risk Lab",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    resolved = await validate_project_access(
        "real-project",
        _MOCK_USER,
        _RepoStub(project),
        settings,
    )

    assert resolved.id == "real-project"
    assert resolved.name == "Real Project"
