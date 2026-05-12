# backend/tests/test_webhooks.py
"""Tests for Phase 7: Webhooks & Report Export."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.foundry import get_foundry_client
from app.services.redis_cache import get_redis_cache


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


def _mock_user(
    tid: str = "local-dev-tenant",
    roles: list[str] | None = None,
) -> CurrentUser:
    return CurrentUser(
        oid="local-dev-user",
        tid=tid,
        name="Dev User",
        email="dev@localhost",
        roles=roles or ["SecurityEngineer", "IAMAdmin", "Executive"],
    )


def _make_mock_repo() -> AsyncMock:
    return AsyncMock(spec=CosmosRepo)


@pytest.fixture()
def mock_repo() -> AsyncMock:
    return _make_mock_repo()


@pytest.fixture()
async def client_with_mock_repo(mock_repo: AsyncMock) -> AsyncClient:
    from app.main import create_app

    test_app = create_app()
    test_app.dependency_overrides[get_settings] = _test_settings
    test_app.dependency_overrides[get_cosmos_repo] = lambda: mock_repo
    test_app.dependency_overrides[get_current_user] = lambda: _mock_user()
    test_app.dependency_overrides[get_foundry_client] = lambda: None
    test_app.dependency_overrides[get_redis_cache] = lambda: None

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture()
async def client_with_executive_only(mock_repo: AsyncMock) -> AsyncClient:
    """Client where user only has Executive role (not IAMAdmin)."""
    from app.main import create_app

    test_app = create_app()
    test_app.dependency_overrides[get_settings] = _test_settings
    test_app.dependency_overrides[get_cosmos_repo] = lambda: mock_repo
    test_app.dependency_overrides[get_current_user] = lambda: _mock_user(
        roles=["Executive"],
    )
    test_app.dependency_overrides[get_foundry_client] = lambda: None
    test_app.dependency_overrides[get_redis_cache] = lambda: None

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Webhook validation tests
# ---------------------------------------------------------------------------

class TestWebhookValidation:
    """Tests for the Graph webhook validation handshake."""

    @pytest.mark.asyncio
    async def test_validation_returns_token_as_text(
        self, client_with_mock_repo: AsyncClient,
    ) -> None:
        """Graph sends validationToken as query param; we must echo it as text/plain."""
        resp = await client_with_mock_repo.post(
            "/api/webhooks/graph?validationToken=abc-123-validation"
        )
        assert resp.status_code == 200
        assert resp.text == "abc-123-validation"
        assert "text/plain" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_validation_rejects_special_chars(
        self, client_with_mock_repo: AsyncClient,
    ) -> None:
        resp = await client_with_mock_repo.post(
            "/api/webhooks/graph?validationToken=token%3Dwith%26special"
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Webhook notification tests
# ---------------------------------------------------------------------------

class TestWebhookNotification:
    """Tests for processing Graph change notifications."""

    @pytest.mark.asyncio
    async def test_notification_processing(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        payload = {
            "value": [
                {
                    "tenantId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "resource": "users/abc",
                    "changeType": "updated",
                },
            ],
        }
        resp = await client_with_mock_repo.post(
            "/api/webhooks/graph",
            json=payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "accepted"
        assert body["notifications_queued"] == 1

    @pytest.mark.asyncio
    async def test_empty_notification_list(
        self, client_with_mock_repo: AsyncClient,
    ) -> None:
        resp = await client_with_mock_repo.post(
            "/api/webhooks/graph",
            json={"value": []},
        )
        assert resp.status_code == 200
        assert resp.json()["notifications_queued"] == 0


# ---------------------------------------------------------------------------
# Subscription endpoint tests
# ---------------------------------------------------------------------------

class TestSubscriptionEndpoints:
    """Tests for subscription management endpoints."""

    @pytest.mark.asyncio
    async def test_create_subscription(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        resp = await client_with_mock_repo.post(
            "/api/tenants/local-dev-tenant/subscriptions/create",
            json={
                "resource": "users",
                "notification_url": "https://example.com/webhook",
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "accepted"
        assert "subscription" in body

    @pytest.mark.asyncio
    async def test_create_subscription_requires_iam_admin(
        self, client_with_executive_only: AsyncClient,
    ) -> None:
        """Executive-only users should be denied subscription creation."""
        resp = await client_with_executive_only.post(
            "/api/tenants/local-dev-tenant/subscriptions/create",
            json={
                "resource": "users",
                "notification_url": "https://example.com/webhook",
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_subscriptions(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        # Mock the internal query used by WebhookHandler.list_subscriptions
        mock_repo._sync_state = MagicMock()

        async def _empty_gen(*args: Any, **kwargs: Any) -> Any:
            return
            yield  # make it an async generator

        mock_repo._sync_state.query_items = MagicMock(return_value=_empty_gen())

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/subscriptions"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["subscriptions"] == []

    @pytest.mark.asyncio
    async def test_list_subscriptions_requires_iam_admin(
        self, client_with_executive_only: AsyncClient,
    ) -> None:
        resp = await client_with_executive_only.get(
            "/api/tenants/local-dev-tenant/subscriptions"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Report endpoint tests
# ---------------------------------------------------------------------------

class TestReportEndpoints:
    """Tests for the /reports API routes."""

    @pytest.mark.asyncio
    async def test_download_pdf_report(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_dashboard_summary.return_value = {
            "total_identities": 10,
            "total_actions": 100,
            "identities_by_type": {},
            "avg_risk_score": 30.0,
            "high_risk_count": 1,
            "drift_alerts_open": 2,
            "drift_alerts_by_severity": {},
            "compliance_score": 85.0,
            "top_risky_identities": [],
            "recommendations_count": 5,
            "avg_reduction_score": 20.0,
        }
        mock_repo.get_tenant_config.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/reports/executive?format=pdf"
        )
        assert resp.status_code == 200
        # Should return content (either PDF or JSON fallback)
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_download_pptx_report(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_dashboard_summary.return_value = {
            "total_identities": 10,
            "total_actions": 100,
            "identities_by_type": {},
            "avg_risk_score": 30.0,
            "high_risk_count": 1,
            "drift_alerts_open": 2,
            "drift_alerts_by_severity": {},
            "compliance_score": 85.0,
            "top_risky_identities": [],
            "recommendations_count": 5,
            "avg_reduction_score": 20.0,
        }
        mock_repo.get_tenant_config.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/reports/executive?format=pptx"
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_invalid_report_format(
        self, client_with_mock_repo: AsyncClient,
    ) -> None:
        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/reports/executive?format=csv"
        )
        assert resp.status_code == 422  # validation error from Query pattern


# ---------------------------------------------------------------------------
# Settings endpoint tests
# ---------------------------------------------------------------------------

class TestSettingsEndpoints:
    """Tests for the /settings API routes."""

    @pytest.mark.asyncio
    async def test_get_settings_not_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_tenant_config.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/settings"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_settings_requires_iam_admin(
        self, client_with_executive_only: AsyncClient,
    ) -> None:
        resp = await client_with_executive_only.get(
            "/api/tenants/local-dev-tenant/settings"
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_settings_not_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_tenant_config.return_value = None

        resp = await client_with_mock_repo.put(
            "/api/tenants/local-dev-tenant/settings",
            json={"sync_schedule_hours": 12},
        )
        assert resp.status_code == 404
