# backend/tests/test_dashboard.py
"""Tests for Phase 6: Executive Dashboard & AI Narratives."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.models.narrative import Narrative, NarrativeScope
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.foundry import FoundryClient, get_foundry_client

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _test_settings() -> Settings:
    return Settings(
        local_mode=True,
        cosmos_endpoint="",
        cosmos_key="",
        redis_host="localhost",
        redis_password="",
        applicationinsights_connection_string="",
    )


def _mock_user(tid: str = "local-dev-tenant") -> CurrentUser:
    return CurrentUser(
        oid="local-dev-user",
        tid=tid,
        name="Dev User",
        email="dev@localhost",
        roles=["SecurityEngineer", "IAMAdmin", "Executive"],
    )


def _make_mock_repo() -> AsyncMock:
    return AsyncMock(spec=CosmosRepo)


def _sample_dashboard_summary() -> dict[str, Any]:
    return {
        "total_identities": 120,
        "total_actions": 5400,
        "identities_by_type": {"User": 80, "ServicePrincipal": 30, "ManagedIdentity": 10},
        "avg_risk_score": 42.5,
        "high_risk_count": 8,
        "drift_alerts_open": 15,
        "drift_alerts_by_severity": {"high": 5, "medium": 7, "low": 3},
        "compliance_score": 78.5,
        "top_risky_identities": [
            {
                "id": "User_abc",
                "display_name": "Admin User",
                "identity_type": "User",
                "risk_score": 92.0,
            },
        ],
        "recommendations_count": 45,
        "avg_reduction_score": 35.2,
    }


def _sample_trends() -> dict[str, Any]:
    today = datetime.now(UTC).date()
    return {
        "risk_score_trend": [
            {"date": (today - timedelta(days=i)).isoformat(), "value": 40.0 + i * 0.5}
            for i in range(30)
        ],
        "drift_alerts_trend": [
            {"date": (today - timedelta(days=i)).isoformat(), "value": float(i % 5)}
            for i in range(30)
        ],
        "actions_trend": [
            {"date": (today - timedelta(days=i)).isoformat(), "value": float(100 + i * 10)}
            for i in range(30)
        ],
    }


@pytest.fixture()
def mock_repo() -> AsyncMock:
    return _make_mock_repo()


@pytest.fixture()
def mock_foundry() -> MagicMock:
    client = MagicMock(spec=FoundryClient)
    client.complete = AsyncMock(return_value="This is a test narrative summary.")
    return client


@pytest.fixture()
async def client_with_mocks(
    mock_repo: AsyncMock,
    mock_foundry: MagicMock,
) -> AsyncClient:
    from app.main import create_app
    from app.services.redis_cache import get_redis_cache

    test_app = create_app()
    test_app.dependency_overrides[get_settings] = _test_settings
    test_app.dependency_overrides[get_cosmos_repo] = lambda: mock_repo
    test_app.dependency_overrides[get_current_user] = lambda: _mock_user()
    test_app.dependency_overrides[get_foundry_client] = lambda: mock_foundry
    test_app.dependency_overrides[get_redis_cache] = lambda: None

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Dashboard endpoint tests
# ---------------------------------------------------------------------------


class TestDashboardEndpoints:
    """Tests for the /dashboard API routes."""

    @pytest.mark.asyncio
    async def test_get_dashboard_returns_summary(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_dashboard_summary.return_value = _sample_dashboard_summary()

        resp = await client_with_mocks.get("/api/tenants/local-dev-tenant/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_identities"] == 120
        assert body["total_actions"] == 5400
        assert body["avg_risk_score"] == 42.5
        assert body["high_risk_count"] == 8
        assert body["drift_alerts_open"] == 15
        assert body["compliance_score"] == 78.5
        assert body["recommendations_count"] == 45
        assert len(body["top_risky_identities"]) == 1

    @pytest.mark.asyncio
    async def test_get_dashboard_has_computed_at(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_dashboard_summary.return_value = _sample_dashboard_summary()

        resp = await client_with_mocks.get("/api/tenants/local-dev-tenant/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "computed_at" in body

    @pytest.mark.asyncio
    async def test_get_trends_returns_30_day_data(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_trends.return_value = _sample_trends()

        resp = await client_with_mocks.get("/api/tenants/local-dev-tenant/dashboard/trends")
        assert resp.status_code == 200
        body = resp.json()
        assert "risk_score_trend" in body
        assert "drift_alerts_trend" in body
        assert "actions_trend" in body
        assert len(body["drift_alerts_trend"]) == 30
        assert len(body["actions_trend"]) == 30

    @pytest.mark.asyncio
    async def test_get_trends_each_point_has_date_and_value(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_trends.return_value = _sample_trends()

        resp = await client_with_mocks.get("/api/tenants/local-dev-tenant/dashboard/trends")
        body = resp.json()
        for point in body["actions_trend"]:
            assert "date" in point
            assert "value" in point


# ---------------------------------------------------------------------------
# Narrative endpoint tests
# ---------------------------------------------------------------------------


class TestNarrativeEndpoints:
    """Tests for the /narratives API routes."""

    @pytest.mark.asyncio
    async def test_get_executive_narrative(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
        mock_foundry: MagicMock,
    ) -> None:
        # No cached narrative
        mock_repo.get_narrative.return_value = None
        mock_repo.get_dashboard_summary.return_value = _sample_dashboard_summary()
        mock_repo.upsert_narrative.return_value = Narrative(
            id="executive_tenant",
            tenant_id="local-dev-tenant",
            scope=NarrativeScope.EXECUTIVE,
            scope_id="tenant",
            content="This is a test narrative summary.",
            generated_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        resp = await client_with_mocks.get("/api/tenants/local-dev-tenant/narratives/executive")
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body
        assert body["scope"] == "executive"

    @pytest.mark.asyncio
    async def test_get_executive_narrative_cached(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
        mock_foundry: MagicMock,
    ) -> None:
        # Return a cached, non-expired narrative
        cached = Narrative(
            id="executive_tenant",
            tenant_id="local-dev-tenant",
            scope=NarrativeScope.EXECUTIVE,
            scope_id="tenant",
            content="Cached narrative content.",
            generated_at=datetime.now(UTC) - timedelta(hours=1),
            expires_at=datetime.now(UTC) + timedelta(hours=23),
        )
        mock_repo.get_narrative.return_value = cached

        resp = await client_with_mocks.get("/api/tenants/local-dev-tenant/narratives/executive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "Cached narrative content."
        # Foundry should NOT have been called since cached is valid
        mock_foundry.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_identity_narrative(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
        mock_foundry: MagicMock,
    ) -> None:
        mock_repo.get_narrative.return_value = None
        mock_repo.get_identity.return_value = None  # identity not found path
        mock_repo.upsert_narrative.return_value = Narrative(
            id="identity_User_abc",
            tenant_id="local-dev-tenant",
            scope=NarrativeScope.IDENTITY,
            scope_id="User_abc",
            content="Identity not found.",
            generated_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        resp = await client_with_mocks.get(
            "/api/tenants/local-dev-tenant/narratives/identity/User_abc"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["scope"] == "identity"

    @pytest.mark.asyncio
    async def test_refresh_narratives_returns_202(
        self,
        client_with_mocks: AsyncClient,
        mock_repo: AsyncMock,
        mock_foundry: MagicMock,
    ) -> None:
        mock_repo.get_dashboard_summary.return_value = _sample_dashboard_summary()
        mock_repo.upsert_narrative.return_value = Narrative(
            id="executive_tenant",
            tenant_id="local-dev-tenant",
            scope=NarrativeScope.EXECUTIVE,
            scope_id="tenant",
            content="Refreshed.",
            generated_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        resp = await client_with_mocks.post("/api/tenants/local-dev-tenant/narratives/refresh")
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "accepted"
