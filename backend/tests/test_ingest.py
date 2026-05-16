# backend/tests/test_ingest.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.models.action import ActionEvent, ActionSource
from app.models.identity import IdentityProfile, IdentityType
from app.models.project import Project, ScanRecord
from app.pipelines.ingest_pipeline import IngestPipeline
from app.services.graph_ingest import GraphIngestService, GraphPermissionError
from app.services.master_repo import get_master_repo
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
    """Create an AsyncMock that mimics MasterRepo method signatures."""
    repo = AsyncMock()
    repo.try_acquire_project_scan_lease.return_value = None
    repo.renew_project_scan_lease.return_value = True
    repo.has_project_scan_lease.return_value = True
    repo.release_project_scan_lease.return_value = None
    return repo


@pytest.fixture()
def mock_repo() -> AsyncMock:
    return _make_mock_repo()


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
# Graph ingest error handling tests
# ---------------------------------------------------------------------------


class TestGraphIngestErrors:
    """Focused tests for Graph ingest retry and error translation."""

    @pytest.mark.asyncio
    async def test_retries_throttled_graph_requests_before_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A transient 429 should be retried with backoff before succeeding."""
        service = GraphIngestService(
            _test_settings(), token_provider=AsyncMock(return_value="token")
        )
        responses = [
            httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"code": "TooManyRequests", "message": "Slow down"}},
            ),
            httpx.Response(200, json={"value": [{"id": "event-1"}]}),
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
        monkeypatch.setattr(
            "app.services.graph_ingest.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient()
        )

        events, delta_link = await service.fetch_audit_logs("tenant-001")

        assert delta_link is None
        assert events == [{"id": "event-1"}]
        assert sleep_calls == [0.0]

    @pytest.mark.asyncio
    async def test_caps_retry_after_delay(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A large Retry-After value should be capped to the configured max backoff."""
        service = GraphIngestService(
            _test_settings(), token_provider=AsyncMock(return_value="token")
        )
        responses = [
            httpx.Response(
                429,
                headers={"Retry-After": "120"},
                json={"error": {"code": "TooManyRequests", "message": "Slow down"}},
            ),
            httpx.Response(200, json={"value": [{"id": "event-1"}]}),
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
        monkeypatch.setattr(
            "app.services.graph_ingest.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient()
        )

        await service.fetch_audit_logs("tenant-001")

        assert sleep_calls == [30.0]

    @pytest.mark.asyncio
    async def test_forbidden_graph_request_raises_permission_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Graph 403s should become a typed permission error with context."""
        service = GraphIngestService(
            _test_settings(), token_provider=AsyncMock(return_value="token")
        )

        async def _get(*args: Any, **kwargs: Any) -> httpx.Response:
            return httpx.Response(
                403,
                json={
                    "error": {
                        "code": "Authorization_RequestDenied",
                        "message": "Insufficient privileges to complete the operation.",
                    }
                },
            )

        class _FakeClient:
            async def __aenter__(self) -> _FakeClient:
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

            get = _get

        monkeypatch.setattr(
            "app.services.graph_ingest.httpx.AsyncClient", lambda *args, **kwargs: _FakeClient()
        )

        with pytest.raises(GraphPermissionError) as exc_info:
            await service.fetch_audit_logs("tenant-001")

        assert "directoryAudits" in str(exc_info.value)
        assert "required Graph permissions" in str(exc_info.value)


class TestIngestPipelineProgress:
    """Focused tests for detailed scan progress emissions."""

    @pytest.mark.asyncio
    async def test_emits_detailed_progress_during_long_running_sections(self) -> None:
        repo = AsyncMock()
        repo.get_sync_state.return_value = None
        repo.get_identity.return_value = None
        repo.append_action_events.return_value = 3

        graph = AsyncMock()

        async def _stream_audit(*args: Any, **kwargs: Any):
            yield [SAMPLE_AUDIT_LOG], None

        async def _stream_signin(*args: Any, **kwargs: Any):
            yield [SAMPLE_SIGN_IN_LOG, SAMPLE_SIGN_IN_LOG_FAILURE], None

        graph.stream_audit_logs = _stream_audit
        graph.stream_sign_in_logs = _stream_signin
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
        assert any("action events already stored incrementally" in message for message in messages)


def _scan_test_settings() -> Settings:
    return Settings(
        local_mode=True,
        cosmos_endpoint="",
        cosmos_key="",
        redis_host="localhost",
        redis_password="",
        encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        applicationinsights_connection_string="",
        scan_function_app_url="https://func-test.azurewebsites.net",
        scan_function_key="test-key",
    )


class TestTriggerScanErrorMapping:
    """Focused tests for scan endpoint error translation (function app dispatch)."""

    @pytest.fixture()
    async def scan_client(
        self, mock_repo: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> AsyncClient:
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
            database_name="project-project-001",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo.list_projects_for_user.return_value = [project]

        monkeypatch.setattr("app.routers.scans.CryptoService.decrypt", lambda self, value: "secret")

        test_app = create_app()
        test_app.dependency_overrides[get_settings] = _scan_test_settings
        test_app.dependency_overrides[get_master_repo] = lambda: mock_repo
        test_app.dependency_overrides[get_current_user] = lambda: _mock_user()
        test_app.state.scan_event_broker = ScanEventBroker()
        test_app.state.scan_tasks = {}

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_trigger_scan_returns_502_on_function_app_failure(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the function app call fails, the endpoint should return 502."""

        async def _fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("Function app unreachable")

        monkeypatch.setattr("app.routers.scans._start_function_app_scan", _fail)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 502
        assert "Failed to start scan orchestration" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_trigger_scan_success_returns_202(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Successful function app dispatch should return 202 with scan ID."""

        async def _ok(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"id": "orch-123", "statusQueryGetUri": "https://func-test/status/orch-123"}

        monkeypatch.setattr("app.routers.scans._start_function_app_scan", _ok)

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "running"
        assert "scan_id" in body
        mock_repo.upsert_scan.assert_awaited()

    @pytest.mark.asyncio
    async def test_trigger_scan_rejects_no_function_app_configured(
        self,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without scan_function_app_url, the endpoint should return 503."""
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
            database_name="project-project-001",
            status="active",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo.list_projects_for_user.return_value = [project]

        test_app = create_app()
        test_app.dependency_overrides[get_settings] = _test_settings
        test_app.dependency_overrides[get_master_repo] = lambda: mock_repo
        test_app.dependency_overrides[get_current_user] = lambda: _mock_user()
        test_app.state.scan_event_broker = ScanEventBroker()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_trigger_scan_conflict_when_already_running(
        self,
        scan_client: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        """If a scan is already running, the endpoint should return 409."""
        running_scan = ScanRecord(
            id="scan-active",
            project_id="project-001",
            target_tenant_id="tenant-001",
            scan_type="incremental",
            auth_mode="app",
            status="running",
            phases=[],
            started_at=datetime.now(UTC),
        )
        mock_repo.get_latest_scan.return_value = running_scan

        resp = await scan_client.post("/api/projects/project-001/scans/trigger")

        assert resp.status_code == 409
        assert "already running" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_trigger_scan_rejects_missing_credentials(
        self,
        mock_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Projects without credentials should get 400."""
        from app.main import create_app

        project = Project(
            id="project-002",
            owner_id="local-dev-user",
            owner_email="dev@localhost",
            name="No Creds",
            target_tenant_id="tenant-001",
            target_tenant_name="Tenant 001",
            client_id="",
            encrypted_client_secret="",
            database_name="project-project-002",
            status="setup",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_repo.list_projects_for_user.return_value = [project]

        test_app = create_app()
        test_app.dependency_overrides[get_settings] = _scan_test_settings
        test_app.dependency_overrides[get_master_repo] = lambda: mock_repo
        test_app.dependency_overrides[get_current_user] = lambda: _mock_user()
        test_app.state.scan_event_broker = ScanEventBroker()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.post("/api/projects/project-002/scans/trigger")

        assert resp.status_code == 400
        assert "credentials" in resp.json()["detail"].lower()

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

        assert ": stream-open\n\n" in first_chunk
        assert "scan.snapshot" not in first_chunk
