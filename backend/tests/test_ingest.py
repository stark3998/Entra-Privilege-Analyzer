# backend/tests/test_ingest.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import httpx
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.pipelines.ingest_pipeline import IngestPipeline
from app.config import Settings, get_settings
from app.models.action import ActionEvent, ActionSource
from app.models.identity import IdentityProfile, IdentityType
from app.services.graph_ingest import GraphIngestService, GraphPermissionError, GraphThrottledError
from app.models.project import Project, ScanRecord
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.scan_events import ScanEventBroker

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
        encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
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
    repo.try_acquire_project_scan_lease.return_value = None
    repo.renew_project_scan_lease.return_value = True
    repo.has_project_scan_lease.return_value = True
    repo.release_project_scan_lease.return_value = None
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


class TestGraphIngestErrors:
    """Focused tests for Graph ingest retry and error translation."""

    @pytest.mark.asyncio
    async def test_retries_throttled_graph_requests_before_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transient 429 should be retried with backoff before succeeding."""
        service = GraphIngestService(_test_settings(), token_provider=AsyncMock(return_value="token"))
        responses = [
            httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"code": "TooManyRequests", "message": "Slow down"}}),
            httpx.Response(200, json={"value": [{"id": "event-1"}]})
        ]
        sleep_calls: list[float] = []

        async def _sleep(delay: float) -> None:
            sleep_calls.append(delay)

        async def _get(*args: Any, **kwargs: Any) -> httpx.Response:
            return responses.pop(0)

        class _FakeClient:
            async def __aenter__(self) -> _FakeClient:
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

            get = _get

        monkeypatch.setattr("app.services.graph_ingest.asyncio.sleep", _sleep)
        monkeypatch.setattr("app.services.graph_ingest.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient())

        events, delta_link = await service.fetch_audit_logs("tenant-001")

        assert delta_link is None
        assert events == [{"id": "event-1"}]
        assert sleep_calls == [0.0]

    @pytest.mark.asyncio
    async def test_caps_retry_after_delay(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A large Retry-After value should be capped to the configured max backoff."""
        service = GraphIngestService(_test_settings(), token_provider=AsyncMock(return_value="token"))
        responses = [
            httpx.Response(429, headers={"Retry-After": "120"}, json={"error": {"code": "TooManyRequests", "message": "Slow down"}}),
            httpx.Response(200, json={"value": [{"id": "event-1"}]})
        ]
        sleep_calls: list[float] = []

        async def _sleep(delay: float) -> None:
            sleep_calls.append(delay)

        async def _get(*args: Any, **kwargs: Any) -> httpx.Response:
            return responses.pop(0)

        class _FakeClient:
            async def __aenter__(self) -> _FakeClient:
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

            get = _get

        monkeypatch.setattr("app.services.graph_ingest.asyncio.sleep", _sleep)
        monkeypatch.setattr("app.services.graph_ingest.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient())

        await service.fetch_audit_logs("tenant-001")

        assert sleep_calls == [30.0]

    @pytest.mark.asyncio
    async def test_forbidden_graph_request_raises_permission_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Graph 403s should become a typed permission error with context."""
        service = GraphIngestService(_test_settings(), token_provider=AsyncMock(return_value="token"))

        async def _get(*args: Any, **kwargs: Any) -> httpx.Response:
            return httpx.Response(
                403,
                json={"error": {"code": "Authorization_RequestDenied", "message": "Insufficient privileges to complete the operation."}},
            )

        class _FakeClient:
            async def __aenter__(self) -> _FakeClient:
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

            get = _get

        monkeypatch.setattr("app.services.graph_ingest.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient())

        with pytest.raises(GraphPermissionError) as exc_info:
            await service.fetch_audit_logs("tenant-001")

        assert "directoryAudits" in str(exc_info.value)
        assert "required Graph permissions" in str(exc_info.value)


class TestIngestPipelineProgress:
    """Focused tests for detailed scan progress emissions."""

    @pytest.mark.asyncio
    async def test_emits_detailed_progress_during_long_running_sections(self) -> None:
        repo = AsyncMock(spec=CosmosRepo)
        repo.get_sync_state.return_value = None
        repo.get_identity.return_value = None
        repo.append_action_events.return_value = 3

        graph = AsyncMock()
        graph.fetch_audit_logs.return_value = ([SAMPLE_AUDIT_LOG], None)
        graph.fetch_sign_in_logs.return_value = [SAMPLE_SIGN_IN_LOG, SAMPLE_SIGN_IN_LOG_FAILURE]
        graph.fetch_users.return_value = [
            {
                "id": "user-oid-123",
                "userPrincipalName": "admin@contoso.com",
                "userType": "Member",
                "externalUserState": None,
                "signInActivity": None,
            },
            {
                "id": "user-oid-456",
                "userPrincipalName": "user@contoso.com",
                "userType": "Member",
                "externalUserState": None,
                "signInActivity": None,
            },
        ]
        graph.fetch_service_principals.return_value = []

        roles_svc = AsyncMock()
        roles_svc.get_identity_roles.return_value = ({}, {})

        progress_events: list[dict[str, Any]] = []

        async def _capture(payload: dict[str, Any]) -> None:
            progress_events.append(payload)

        pipeline = IngestPipeline(repo, graph, roles_svc, progress_callback=_capture)

        await pipeline.run("tenant-001")

        messages = [event.get("message", "") for event in progress_events]
        assert any("Parsed 3 directory events for 2 identities" in message for message in messages)
        assert any("Fetching directory users" in message for message in messages)
        assert any("Fetched 2 users" in message for message in messages)
        assert any("Fetching service principals" in message for message in messages)
        assert any("Processed 2 identity profiles" in message for message in messages)
        assert any("Persisting 3 action events" in message for message in messages)


class TestTriggerScanErrorMapping:
    """Focused tests for scan endpoint error translation."""

    @staticmethod
    async def _wait_for_background_scan_write(mock_repo: AsyncMock) -> None:
        for _ in range(20):
            if mock_repo.upsert_scan.await_count >= 2:
                return
            await asyncio.sleep(0)
        raise AssertionError("background scan task did not persist final state")

    @pytest.fixture()
    async def scan_client(self, mock_repo: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
        from app.main import create_app

        project = Project(
            id="project-001",
            owner_id="local-dev-user",
            owner_email="dev@localhost",
            name="Test Project",
            target_tenant_id="tenant-001",
            target_tenant_name="Tenant 001",
            client_id="client-id",
            encrypted_client_secret="encrypted",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo.list_projects_for_user.return_value = [project]
        mock_repo.try_acquire_project_scan_lease.return_value = project
        mock_repo.release_project_scan_lease.return_value = project

        monkeypatch.setattr("app.routers.scans.CryptoService.decrypt", lambda self, value: "secret")

        test_app = create_app()
        test_app.dependency_overrides[get_settings] = _test_settings
        test_app.dependency_overrides[get_cosmos_repo] = lambda: mock_repo
        test_app.dependency_overrides[get_current_user] = lambda: _mock_user()
        test_app.state.scan_event_broker = ScanEventBroker()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_trigger_scan_returns_controlled_forbidden_error(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A delegated/app Graph permission failure should be persisted after the async 202 response."""
        async def _run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise GraphPermissionError(
                "Microsoft Graph denied access to https://graph.microsoft.com/beta/auditLogs/directoryAudits. Check that the configured identity has the required Graph permissions.",
                status_code=403,
                endpoint="https://graph.microsoft.com/beta/auditLogs/directoryAudits",
                code="Authorization_RequestDenied",
            )

        monkeypatch.setattr("app.routers.scans.IngestPipeline.run", _run)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 202
        await self._wait_for_background_scan_write(mock_repo)
        persisted_scan = mock_repo.upsert_scan.await_args_list[-1].args[0]
        assert "required delegated or application permissions" in persisted_scan.error_message

    @pytest.mark.asyncio
    async def test_trigger_scan_rejects_missing_bearer_before_persisting_scan(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        resp = await scan_client.post(
            "/api/projects/project-001/scans/trigger?auth_mode=delegated"
        )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing Bearer token"
        mock_repo.upsert_scan.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_trigger_scan_returns_controlled_throttled_error(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Graph throttling should be persisted after the async 202 response."""
        async def _run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise GraphThrottledError(
                "Microsoft Graph throttled requests to https://graph.microsoft.com/beta/auditLogs/directoryAudits after retrying.",
                status_code=429,
                endpoint="https://graph.microsoft.com/beta/auditLogs/directoryAudits",
                code="TooManyRequests",
            )

        monkeypatch.setattr("app.routers.scans.IngestPipeline.run", _run)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 202
        await self._wait_for_background_scan_write(mock_repo)
        persisted_scan = mock_repo.upsert_scan.await_args_list[-1].args[0]
        assert "Please wait and try again" in persisted_scan.error_message

    @pytest.mark.asyncio
    async def test_trigger_scan_fails_cleanly_when_queue_event_cannot_publish(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def _publish(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("redis unavailable")

        monkeypatch.setattr("app.routers.scans._publish_scan_event", _publish)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "Scan event streaming is temporarily unavailable. Retry the scan."
        assert mock_repo.upsert_scan.await_count >= 2
        persisted_scan = mock_repo.upsert_scan.await_args_list[-1].args[0]
        assert persisted_scan.status == "failed"
        assert persisted_scan.error_message == resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_trigger_scan_returns_sanitized_internal_error(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unexpected failures should be sanitized in persisted state after the async 202 response."""

        async def _run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

        monkeypatch.setattr("app.routers.scans.IngestPipeline.run", _run)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 202
        await self._wait_for_background_scan_write(mock_repo)
        persisted_scan = mock_repo.upsert_scan.await_args_list[-1].args[0]
        assert persisted_scan.error_message == "Scan failed due to an internal server error. Check backend logs for details."

    @pytest.mark.asyncio
    async def test_trigger_scan_reclaims_expired_running_scan(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        persisted_scans: list[ScanRecord] = []

        stale_started_at = datetime.now(UTC) - timedelta(minutes=10)
        stale_scan = ScanRecord(
            id="scan-stale",
            project_id="project-001",
            target_tenant_id="tenant-001",
            scan_type="incremental",
            status="running",
            auth_mode="app",
            phases=[],
            started_at=stale_started_at,
            owner_instance_id="other-instance",
            heartbeat_at=stale_started_at,
            lease_expires_at=stale_started_at + timedelta(seconds=30),
        )

        async def _run(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"identities_processed": 1}

        async def _upsert_scan(scan: ScanRecord) -> ScanRecord:
            persisted_scans.append(scan.model_copy(deep=True))
            return scan

        mock_repo.get_latest_scan.return_value = stale_scan
        mock_repo.try_acquire_project_scan_lease.return_value = Project(
            id="project-001",
            owner_id="local-dev-user",
            owner_email="dev@localhost",
            name="Test Project",
            target_tenant_id="tenant-001",
            target_tenant_name="Tenant 001",
            client_id="client-id",
            encrypted_client_secret="encrypted",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo.upsert_scan.side_effect = _upsert_scan
        monkeypatch.setattr("app.routers.scans.IngestPipeline.run", _run)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 202
        assert len(persisted_scans) >= 2
        reclaimed_scan = persisted_scans[0]
        assert reclaimed_scan.id == "scan-stale"
        assert reclaimed_scan.status == "failed"
        assert reclaimed_scan.error_message == "Scan abandoned after backend restart or task loss."
        new_scan_writes = [
            scan
            for scan in persisted_scans[1:]
            if scan.id != "scan-stale"
        ]
        assert new_scan_writes
        assert any(scan.status in {"running", "completed"} for scan in new_scan_writes)
        running_writes = [scan for scan in new_scan_writes if scan.status == "running"]
        completed_writes = [scan for scan in new_scan_writes if scan.status == "completed"]
        assert running_writes
        assert all(scan.owner_instance_id is not None for scan in running_writes)
        assert all(scan.heartbeat_at is not None for scan in running_writes)
        assert all(scan.lease_expires_at is not None for scan in running_writes)
        assert all(scan.owner_instance_id is None for scan in completed_writes)
        assert all(scan.heartbeat_at is None for scan in completed_writes)
        assert all(scan.lease_expires_at is None for scan in completed_writes)

    @pytest.mark.asyncio
    async def test_stream_scan_events_emits_immediate_snapshot_for_active_scan(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        active_scan = ScanRecord(
            id="scan-active",
            project_id="project-001",
            target_tenant_id="tenant-001",
            scan_type="full",
            auth_mode="app",
            status="running",
            phases=[
                {
                    "name": "audit_logs",
                    "status": "running",
                    "started_at": datetime.now(UTC),
                    "completed_at": None,
                    "items_processed": 0,
                }
            ],
            started_at=datetime.now(UTC),
        )
        mock_repo.get_latest_scan.return_value = active_scan

        async with scan_client.stream(
            "GET",
            f"/api/projects/project-001/scans/events?scan_id={active_scan.id}",
        ) as response:
            assert response.status_code == 200
            first_chunk = await response.aiter_text().__anext__()

        assert ": stream-open\n\n" in first_chunk
        assert "event: scan.snapshot" in first_chunk
        assert '"scan_id":"scan-active"' in first_chunk
        assert '"status":"running"' in first_chunk
        assert '"snapshot":true' in first_chunk

    @pytest.mark.asyncio
    async def test_stream_scan_events_emits_immediate_open_frame_without_snapshot(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_latest_scan.return_value = None

        async with scan_client.stream(
            "GET",
            "/api/projects/project-001/scans/events?scan_id=scan-missing",
        ) as response:
            assert response.status_code == 200
            first_chunk = await response.aiter_text().__anext__()

        assert first_chunk == ": stream-open\n\n"

    @pytest.mark.asyncio
    async def test_run_scan_task_marks_scan_failed_after_lease_loss_cancellation(
        self,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.routers.scans import _run_scan_task

        persisted_scans: list[ScanRecord] = []
        project = Project(
            id="project-001",
            owner_id="local-dev-user",
            owner_email="dev@localhost",
            name="Test Project",
            target_tenant_id="tenant-001",
            target_tenant_name="Tenant 001",
            client_id="client-id",
            encrypted_client_secret="encrypted",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        scan = ScanRecord(
            id="scan-lease-loss",
            project_id=project.id,
            target_tenant_id=project.target_tenant_id,
            scan_type="incremental",
            auth_mode="app",
            status="running",
            phases=[],
            started_at=datetime.now(UTC),
            owner_instance_id="instance-1",
            heartbeat_at=datetime.now(UTC),
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=1),
        )

        async def _upsert_scan(saved_scan: ScanRecord) -> ScanRecord:
            persisted_scans.append(saved_scan.model_copy(deep=True))
            return saved_scan

        async def _run_pipeline(*args: Any, **kwargs: Any) -> dict[str, Any]:
            await asyncio.sleep(3600)
            return {"identities_processed": 1}

        class _FakeGraphIngestService:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

        class _FakeGraphRolesService:
            def __init__(self, graph: Any) -> None:
                self.graph = graph

        mock_repo.upsert_scan.side_effect = _upsert_scan
        mock_repo.renew_project_scan_lease.return_value = False
        mock_repo.release_project_scan_lease.return_value = None
        monkeypatch.setattr("app.routers.scans._SCAN_HEARTBEAT_INTERVAL_SECONDS", 0.01)
        monkeypatch.setattr("app.routers.scans.CryptoService.decrypt", lambda self, value: "secret")
        monkeypatch.setattr("app.routers.scans.GraphIngestService", _FakeGraphIngestService)
        monkeypatch.setattr("app.routers.scans.GraphRolesService", _FakeGraphRolesService)
        monkeypatch.setattr("app.routers.scans.IngestPipeline.run", _run_pipeline)

        app = SimpleNamespace(
            state=SimpleNamespace(
                scan_event_broker=ScanEventBroker(),
                instance_id="instance-1",
            )
        )

        await _run_scan_task(
            app,
            mock_repo,
            project,
            scan,
            full=False,
            auth_mode="app",
            bearer_token=None,
            settings=_test_settings(),
        )

        assert persisted_scans
        final_scan = persisted_scans[-1]
        assert final_scan.id == scan.id
        assert final_scan.status == "failed"
        assert final_scan.error_message == "Scan abandoned after backend restart or task loss."
        assert final_scan.completed_at is not None
        assert final_scan.owner_instance_id is None
        assert final_scan.heartbeat_at is None
        assert final_scan.lease_expires_at is None

