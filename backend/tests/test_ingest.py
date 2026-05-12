# backend/tests/test_ingest.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.models.action import ActionEvent, ActionSource
from app.models.identity import IdentityProfile, IdentityType
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.graph_ingest import GraphIngestService

# ---------------------------------------------------------------------------
# Sample raw Graph API payloads
# ---------------------------------------------------------------------------

SAMPLE_AUDIT_LOG: dict[str, Any] = {
    "id": "Directory_abc123",
    "category": "UserManagement",
    "activityDisplayName": "Add user",
    "activityDateTime": "2024-01-15T10:30:00Z",
    "result": "success",
    "correlationId": "corr-001",
    "initiatedBy": {
        "user": {
            "id": "user-oid-123",
            "displayName": "Admin User",
            "userPrincipalName": "admin@contoso.com",
        }
    },
    "targetResources": [
        {
            "id": "target-user-id",
            "displayName": "New User",
            "type": "User",
        }
    ],
}

SAMPLE_AUDIT_LOG_APP_ACTOR: dict[str, Any] = {
    "id": "Directory_def456",
    "category": "ApplicationManagement",
    "activityDisplayName": "Update application",
    "activityDateTime": "2024-02-20T14:00:00Z",
    "result": "success",
    "correlationId": "corr-002",
    "initiatedBy": {
        "app": {
            "id": "sp-oid-999",
            "displayName": "My Service Principal",
        }
    },
    "targetResources": [
        {
            "id": "app-resource-id",
            "displayName": "Target App",
            "type": "Application",
        }
    ],
}

SAMPLE_SIGN_IN_LOG: dict[str, Any] = {
    "id": "signin-789",
    "createdDateTime": "2024-01-16T08:00:00Z",
    "userId": "user-oid-123",
    "userDisplayName": "Admin User",
    "userPrincipalName": "admin@contoso.com",
    "appId": "app-id-001",
    "appDisplayName": "Azure Portal",
    "resourceDisplayName": "Microsoft Graph",
    "correlationId": "corr-003",
    "ipAddress": "203.0.113.42",
    "status": {"errorCode": 0, "failureReason": ""},
}

SAMPLE_SIGN_IN_LOG_FAILURE: dict[str, Any] = {
    "id": "signin-fail-001",
    "createdDateTime": "2024-01-17T09:00:00Z",
    "userId": "user-oid-456",
    "userDisplayName": "Regular User",
    "userPrincipalName": "user@contoso.com",
    "appId": "app-id-002",
    "appDisplayName": "My App",
    "resourceDisplayName": "SharePoint",
    "correlationId": "corr-004",
    "ipAddress": "198.51.100.10",
    "status": {"errorCode": 50053, "failureReason": "Account locked"},
}


# ---------------------------------------------------------------------------
# Test fixtures
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
    """Create an AsyncMock that mimics CosmosRepo method signatures."""
    repo = AsyncMock(spec=CosmosRepo)
    return repo


@pytest.fixture()
def mock_repo() -> AsyncMock:
    return _make_mock_repo()


@pytest.fixture()
async def client_with_mock_repo(mock_repo: AsyncMock) -> AsyncClient:
    """AsyncClient with both settings and cosmos repo mocked."""
    from app.main import create_app

    test_app = create_app()
    test_app.dependency_overrides[get_settings] = _test_settings
    test_app.dependency_overrides[get_cosmos_repo] = lambda: mock_repo
    test_app.dependency_overrides[get_current_user] = lambda: _mock_user()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# parse_audit_event tests
# ---------------------------------------------------------------------------

class TestParseAuditEvent:
    """Tests for GraphIngestService.parse_audit_event."""

    def test_parses_user_initiated_audit(self) -> None:
        """A user-initiated audit log should produce a correct ActionEvent."""
        event, actor_id, actor_name = GraphIngestService.parse_audit_event(
            "tenant-001", SAMPLE_AUDIT_LOG
        )

        assert isinstance(event, ActionEvent)
        assert event.tenant_id == "tenant-001"
        assert event.action == "Add user"
        assert event.result == "success"
        assert event.source == ActionSource.AUDIT_LOG
        assert event.resource == "New User"
        assert event.resource_type == "User"
        assert event.correlation_id == "corr-001"
        assert event.identity_id == "User_user-oid-123"
        assert event.identity_display_name == "Admin User"
        assert actor_id == "user-oid-123"
        assert actor_name == "Admin User"
        assert event.timestamp == datetime(2024, 1, 15, 10, 30, tzinfo=UTC)

    def test_parses_app_initiated_audit(self) -> None:
        """A service-principal-initiated audit log should use the app actor."""
        event, actor_id, actor_name = GraphIngestService.parse_audit_event(
            "tenant-001", SAMPLE_AUDIT_LOG_APP_ACTOR
        )

        assert event.action == "Update application"
        assert event.identity_id == "ServicePrincipal_sp-oid-999"
        assert event.identity_display_name == "My Service Principal"
        assert actor_id == "sp-oid-999"
        assert actor_name == "My Service Principal"
        assert event.resource == "Target App"
        assert event.resource_type == "Application"

    def test_deterministic_id_is_stable(self) -> None:
        """The same raw event should always produce the same event ID."""
        event_a, _, _ = GraphIngestService.parse_audit_event("t1", SAMPLE_AUDIT_LOG)
        event_b, _, _ = GraphIngestService.parse_audit_event("t1", SAMPLE_AUDIT_LOG)
        assert event_a.id == event_b.id

    def test_different_tenants_produce_different_ids(self) -> None:
        """Events for different tenants should have different IDs."""
        event_a, _, _ = GraphIngestService.parse_audit_event("tenant-A", SAMPLE_AUDIT_LOG)
        event_b, _, _ = GraphIngestService.parse_audit_event("tenant-B", SAMPLE_AUDIT_LOG)
        assert event_a.id != event_b.id


# ---------------------------------------------------------------------------
# parse_sign_in_event tests
# ---------------------------------------------------------------------------

class TestParseSignInEvent:
    """Tests for GraphIngestService.parse_sign_in_event."""

    def test_parses_successful_sign_in(self) -> None:
        """A successful sign-in should produce a 'success' ActionEvent."""
        event, actor_id, actor_name = GraphIngestService.parse_sign_in_event(
            "tenant-001", SAMPLE_SIGN_IN_LOG
        )

        assert isinstance(event, ActionEvent)
        assert event.tenant_id == "tenant-001"
        assert event.action == "Sign-in"
        assert event.result == "success"
        assert event.source == ActionSource.SIGN_IN_LOG
        assert event.resource == "Microsoft Graph"
        assert event.ip_address == "203.0.113.42"
        assert event.identity_id == "User_user-oid-123"
        assert actor_id == "user-oid-123"
        assert actor_name == "Admin User"
        assert event.timestamp == datetime(2024, 1, 16, 8, 0, tzinfo=UTC)

    def test_parses_failed_sign_in(self) -> None:
        """A failed sign-in (non-zero errorCode) should produce result='failure'."""
        event, actor_id, actor_name = GraphIngestService.parse_sign_in_event(
            "tenant-001", SAMPLE_SIGN_IN_LOG_FAILURE
        )

        assert event.result == "failure"
        assert event.identity_id == "User_user-oid-456"
        assert actor_id == "user-oid-456"
        assert actor_name == "Regular User"

    def test_sign_in_deterministic_id(self) -> None:
        """Same raw sign-in should always produce the same event ID."""
        event_a, _, _ = GraphIngestService.parse_sign_in_event("t1", SAMPLE_SIGN_IN_LOG)
        event_b, _, _ = GraphIngestService.parse_sign_in_event("t1", SAMPLE_SIGN_IN_LOG)
        assert event_a.id == event_b.id


# ---------------------------------------------------------------------------
# Identity list endpoint tests (mocked cosmos)
# ---------------------------------------------------------------------------

class TestListIdentitiesEndpoint:
    """Tests for GET /api/tenants/{tid}/identities."""

    @pytest.mark.asyncio
    async def test_returns_paginated_results(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock
    ) -> None:
        """The endpoint should return items, total, page, size."""
        now = datetime.now(UTC)
        profiles = [
            IdentityProfile(
                id="User_abc",
                tenant_id="local-dev-tenant",
                identity_type=IdentityType.USER,
                object_id="abc",
                display_name="Alice",
                upn="alice@contoso.com",
                created_at=now,
                updated_at=now,
            ),
            IdentityProfile(
                id="ServicePrincipal_def",
                tenant_id="local-dev-tenant",
                identity_type=IdentityType.SERVICE_PRINCIPAL,
                object_id="def",
                display_name="My App SP",
                app_id="app-def",
                created_at=now,
                updated_at=now,
            ),
        ]
        mock_repo.list_identities.return_value = (profiles, 2)

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/identities?page=1&size=50"
        )
        assert resp.status_code == 200

        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["size"] == 50
        assert len(body["items"]) == 2
        assert body["items"][0]["display_name"] == "Alice"
        assert body["items"][1]["display_name"] == "My App SP"

    @pytest.mark.asyncio
    async def test_empty_results(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock
    ) -> None:
        """When no identities exist, return an empty list with total=0."""
        mock_repo.list_identities.return_value = ([], 0)

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/identities"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0


# ---------------------------------------------------------------------------
# Tenant-ID validation tests
# ---------------------------------------------------------------------------

class TestTenantIdValidation:
    """Ensure requests for a different tenant are rejected when not in local mode."""

    @pytest.mark.asyncio
    async def test_cross_tenant_rejected_in_prod_mode(self) -> None:
        """A user from tenant A requesting tenant B data should get 403."""
        from app.main import create_app

        def _prod_settings() -> Settings:
            return Settings(
                local_mode=False,
                cosmos_endpoint="",
                cosmos_key="",
            )

        def _user_tenant_a() -> CurrentUser:
            return CurrentUser(
                oid="user-oid",
                tid="tenant-A",
                name="User A",
                email="a@tenant-a.com",
                roles=["IAMAdmin"],
            )

        repo_mock = _make_mock_repo()
        repo_mock.list_identities.return_value = ([], 0)

        test_app = create_app()
        test_app.dependency_overrides[get_settings] = _prod_settings
        test_app.dependency_overrides[get_cosmos_repo] = lambda: repo_mock
        test_app.dependency_overrides[get_current_user] = _user_tenant_a

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/api/tenants/tenant-B/identities")
            assert resp.status_code == 403
            assert "Cross-tenant" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_same_tenant_allowed_in_prod_mode(self) -> None:
        """A user requesting their own tenant's data should succeed."""
        from app.main import create_app

        def _prod_settings() -> Settings:
            return Settings(
                local_mode=False,
                cosmos_endpoint="",
                cosmos_key="",
            )

        def _user_tenant_a() -> CurrentUser:
            return CurrentUser(
                oid="user-oid",
                tid="tenant-A",
                name="User A",
                email="a@tenant-a.com",
                roles=["IAMAdmin"],
            )

        repo_mock = _make_mock_repo()
        repo_mock.list_identities.return_value = ([], 0)

        test_app = create_app()
        test_app.dependency_overrides[get_settings] = _prod_settings
        test_app.dependency_overrides[get_cosmos_repo] = lambda: repo_mock
        test_app.dependency_overrides[get_current_user] = _user_tenant_a

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.get("/api/tenants/tenant-A/identities")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_local_mode_allows_any_tenant(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock
    ) -> None:
        """In LOCAL_MODE, any tenant_id should be allowed."""
        mock_repo.list_identities.return_value = ([], 0)

        resp = await client_with_mock_repo.get(
            "/api/tenants/any-random-tenant/identities"
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Get identity endpoint tests
# ---------------------------------------------------------------------------

class TestGetIdentityEndpoint:
    """Tests for GET /api/tenants/{tid}/identities/{id}."""

    @pytest.mark.asyncio
    async def test_returns_identity(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock
    ) -> None:
        """Should return the identity profile when found."""
        now = datetime.now(UTC)
        profile = IdentityProfile(
            id="User_abc",
            tenant_id="local-dev-tenant",
            identity_type=IdentityType.USER,
            object_id="abc",
            display_name="Alice",
            created_at=now,
            updated_at=now,
        )
        mock_repo.get_identity.return_value = profile

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/identities/User_abc"
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock
    ) -> None:
        """Should return 404 when the identity does not exist."""
        mock_repo.get_identity.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/identities/User_nonexistent"
        )
        assert resp.status_code == 404
