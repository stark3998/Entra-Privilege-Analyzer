# backend/tests/test_auth.py
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz_returns_ok(client: AsyncClient) -> None:
    """GET /healthz should always return 200."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_tenants_me_local_mode(client: AsyncClient) -> None:
    """In LOCAL_MODE, GET /api/tenants/me should return the mock user."""
    resp = await client.get("/api/tenants/me")
    assert resp.status_code == 200

    body = resp.json()
    assert body["tenant_id"] == "local-dev-tenant"
    assert body["name"] == "Dev User"
    assert body["email"] == "dev@localhost"
    assert set(body["roles"]) == {"SecurityEngineer", "IAMAdmin", "Executive"}


@pytest.mark.asyncio
async def test_tenants_me_has_all_three_roles(client: AsyncClient) -> None:
    """The mock user in LOCAL_MODE must carry all three app roles."""
    resp = await client.get("/api/tenants/me")
    roles = resp.json()["roles"]
    assert len(roles) == 3
    for role in ("SecurityEngineer", "IAMAdmin", "Executive"):
        assert role in roles
