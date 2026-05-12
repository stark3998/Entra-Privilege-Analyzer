# backend/tests/test_drift.py
"""Tests for Phase 4: Permission Drift Detection."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.models.drift import (
    BaselineStats,
    DriftAlert,
    DriftSeverity,
    DriftStatus,
    DriftType,
)
from app.models.identity import (
    CurrentRole,
    IdentityProfile,
    IdentityType,
    ObservedAction,
)
from app.models.role import PermissionGap
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.drift_detector import DriftDetector
from app.services.risk_scorer import RiskScorer


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


def _sample_profile(
    *,
    actions: list[tuple[str, int]] | None = None,
    roles: list[CurrentRole] | None = None,
    last_seen: datetime | None = None,
    identity_type: IdentityType = IdentityType.USER,
) -> IdentityProfile:
    """Build a minimal IdentityProfile for testing.

    actions is a list of (action_name, count) tuples.
    """
    now = datetime.now(UTC)
    observed = [
        ObservedAction(
            action=a,
            resource="test-resource",
            count=c,
            first_seen=now,
            last_seen=now,
        )
        for a, c in (actions or [])
    ]
    return IdentityProfile(
        id="User_abc12345",
        tenant_id="test-tenant",
        identity_type=identity_type,
        object_id="abc12345",
        display_name="Test User",
        upn="test@contoso.com",
        current_roles=roles or [],
        observed_actions=observed,
        risk_score=0.0,
        action_count=sum(c for _, c in (actions or [])),
        last_seen=last_seen or now,
        first_seen=now,
        created_at=now,
        updated_at=now,
    )


def _sample_baseline(
    action: str,
    mean: float,
    stddev: float,
    sample_count: int = 10,
) -> BaselineStats:
    now = datetime.now(UTC)
    return BaselineStats(
        id=f"User_abc12345_{action[:8]}",
        identity_id="User_abc12345",
        tenant_id="test-tenant",
        action=action,
        resource="test-resource",
        mean=mean,
        stddev=stddev,
        sample_count=sample_count,
        window_start=now - timedelta(days=30),
        window_end=now,
        updated_at=now,
    )


def _sample_drift_alert(
    *,
    severity: DriftSeverity = DriftSeverity.HIGH,
    status: DriftStatus = DriftStatus.OPEN,
) -> DriftAlert:
    return DriftAlert(
        id="alert-001",
        tenant_id="test-tenant",
        identity_id="User_abc12345",
        identity_display_name="Test User",
        drift_type=DriftType.FIRST_SEEN,
        action="Add user",
        severity=severity,
        status=status,
        details="Test drift alert",
        detected_at=datetime.now(UTC),
    )


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

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# First-seen detection tests
# ---------------------------------------------------------------------------

class TestFirstSeenDetection:
    """Tests for DriftDetector.detect_first_seen."""

    @pytest.mark.asyncio
    async def test_known_actions_no_alerts(self, mock_repo: AsyncMock) -> None:
        """Actions in the baseline should not produce alerts."""
        profile = _sample_profile(actions=[("Add user", 5), ("Delete user", 2)])
        baseline_actions = {"Add user", "Delete user"}

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_first_seen("test-tenant", profile, baseline_actions)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_unknown_action_produces_alert(self, mock_repo: AsyncMock) -> None:
        """An action NOT in the baseline should produce a first-seen alert."""
        profile = _sample_profile(actions=[("Add user", 5), ("Grant admin consent", 1)])
        baseline_actions = {"Add user"}

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_first_seen("test-tenant", profile, baseline_actions)

        assert len(alerts) == 1
        assert alerts[0].drift_type == DriftType.FIRST_SEEN
        assert alerts[0].action == "Grant admin consent"
        assert alerts[0].status == DriftStatus.OPEN

    @pytest.mark.asyncio
    async def test_empty_baseline_all_actions_drift(self, mock_repo: AsyncMock) -> None:
        """With no baseline, every observed action is first-seen."""
        profile = _sample_profile(actions=[("Add user", 1), ("Delete user", 1)])
        baseline_actions: set[str] = set()

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_first_seen("test-tenant", profile, baseline_actions)

        assert len(alerts) == 2


# ---------------------------------------------------------------------------
# Frequency anomaly detection tests
# ---------------------------------------------------------------------------

class TestFrequencyAnomalyDetection:
    """Tests for DriftDetector.detect_frequency_anomaly."""

    @pytest.mark.asyncio
    async def test_high_z_score_triggers_alert(self, mock_repo: AsyncMock) -> None:
        """An action with z > 3.0 should produce a high severity alert."""
        # baseline: mean=2.0, stddev=1.0, observed count=10 -> z = (10-2)/1 = 8.0
        profile = _sample_profile(actions=[("Add user", 10)])
        baselines = [_sample_baseline("Add user", mean=2.0, stddev=1.0)]

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_frequency_anomaly("test-tenant", profile, baselines)

        assert len(alerts) == 1
        assert alerts[0].drift_type == DriftType.FREQUENCY_ANOMALY
        assert alerts[0].severity == DriftSeverity.HIGH
        assert alerts[0].z_score is not None
        assert alerts[0].z_score > 3.0

    @pytest.mark.asyncio
    async def test_medium_z_score_triggers_alert(self, mock_repo: AsyncMock) -> None:
        """z between 2.0 and 3.0 should produce a medium severity alert."""
        # mean=5.0, stddev=2.0, count=10 -> z = (10-5)/2 = 2.5
        profile = _sample_profile(actions=[("Add user", 10)])
        baselines = [_sample_baseline("Add user", mean=5.0, stddev=2.0)]

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_frequency_anomaly("test-tenant", profile, baselines)

        assert len(alerts) == 1
        assert alerts[0].severity == DriftSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_low_z_score_no_alert(self, mock_repo: AsyncMock) -> None:
        """z < 1.5 should not produce an alert."""
        # mean=9.0, stddev=2.0, count=10 -> z = (10-9)/2 = 0.5
        profile = _sample_profile(actions=[("Add user", 10)])
        baselines = [_sample_baseline("Add user", mean=9.0, stddev=2.0)]

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_frequency_anomaly("test-tenant", profile, baselines)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_insufficient_samples_skipped(self, mock_repo: AsyncMock) -> None:
        """Baselines with < 7 samples should be skipped."""
        profile = _sample_profile(actions=[("Add user", 100)])
        baselines = [_sample_baseline("Add user", mean=2.0, stddev=1.0, sample_count=3)]

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_frequency_anomaly("test-tenant", profile, baselines)

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_zero_stddev_skipped(self, mock_repo: AsyncMock) -> None:
        """Baselines with stddev=0 should be skipped to avoid division by zero."""
        profile = _sample_profile(actions=[("Add user", 100)])
        baselines = [_sample_baseline("Add user", mean=2.0, stddev=0.0)]

        detector = DriftDetector(mock_repo)
        alerts = await detector.detect_frequency_anomaly("test-tenant", profile, baselines)

        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Risk scorer tests
# ---------------------------------------------------------------------------

class TestRiskScorer:
    """Tests for RiskScorer.compute_risk_score."""

    def test_zero_risk_for_clean_identity(self) -> None:
        """An active identity with no drift, no gaps, no admin roles -> low score."""
        profile = _sample_profile(actions=[("Add user", 1)])
        scorer = RiskScorer()
        score = scorer.compute_risk_score(profile, [], [])
        assert score == 0.0

    def test_drift_alerts_increase_score(self) -> None:
        """Active drift alerts should raise the drift component."""
        profile = _sample_profile(actions=[("Add user", 1)])
        alerts = [
            _sample_drift_alert(severity=DriftSeverity.HIGH),
            _sample_drift_alert(severity=DriftSeverity.CRITICAL),
        ]
        scorer = RiskScorer()
        score = scorer.compute_risk_score(profile, alerts, [])
        assert score > 0.0

    def test_permission_gaps_increase_score(self) -> None:
        """Overprivilege gaps should raise the overprivilege component."""
        profile = _sample_profile(
            actions=[("Add user", 1)],
            roles=[
                CurrentRole(role_id="r1", role_name="User.ReadWrite.All", scope="/"),
                CurrentRole(role_id="r2", role_name="Directory.ReadWrite.All", scope="/"),
            ],
        )
        gaps = [
            PermissionGap(permission="Directory.ReadWrite.All", risk_weight="high", is_used=False),
        ]
        scorer = RiskScorer()
        score = scorer.compute_risk_score(profile, [], gaps)
        assert score > 0.0

    def test_permanent_admin_increases_score(self) -> None:
        """Permanent Global Administrator should produce a high admin component."""
        profile = _sample_profile(
            actions=[("Add user", 1)],
            roles=[
                CurrentRole(
                    role_id="ga",
                    role_name="Global Administrator",
                    scope="/",
                    is_permanent=True,
                ),
            ],
        )
        scorer = RiskScorer()
        score = scorer.compute_risk_score(profile, [], [])
        # 20% weight * 50 (Global Admin permanent) = 10
        assert score >= 10.0

    def test_stale_identity_increases_score(self) -> None:
        """An identity inactive for 120 days should have a stale access penalty."""
        old_date = datetime.now(UTC) - timedelta(days=120)
        profile = _sample_profile(actions=[], last_seen=old_date)
        scorer = RiskScorer()
        score = scorer.compute_risk_score(profile, [], [])
        # 20% weight * 100 (>90 days) = 20
        assert score >= 20.0

    def test_score_capped_at_100(self) -> None:
        """Score should never exceed 100."""
        old_date = datetime.now(UTC) - timedelta(days=365)
        profile = _sample_profile(
            actions=[("Add user", 1)],
            roles=[
                CurrentRole(
                    role_id="ga",
                    role_name="Global Administrator",
                    scope="/",
                    is_permanent=True,
                ),
            ],
            last_seen=old_date,
        )
        alerts = [_sample_drift_alert(severity=DriftSeverity.CRITICAL) for _ in range(20)]
        gaps = [
            PermissionGap(permission=f"Perm.{i}", risk_weight="high", is_used=False)
            for i in range(50)
        ]
        scorer = RiskScorer()
        score = scorer.compute_risk_score(profile, alerts, gaps)
        assert score <= 100.0


# ---------------------------------------------------------------------------
# Drift alert endpoint tests
# ---------------------------------------------------------------------------

class TestDriftAlertEndpoints:
    """Tests for the /drift-alerts API routes."""

    @pytest.mark.asyncio
    async def test_list_drift_alerts(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        alert = _sample_drift_alert()
        mock_repo.list_drift_alerts.return_value = ([alert], 1)

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/drift-alerts"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "Add user"

    @pytest.mark.asyncio
    async def test_get_drift_alert_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        alert = _sample_drift_alert()
        mock_repo.get_drift_alert.return_value = alert

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/drift-alerts/alert-001"
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "alert-001"

    @pytest.mark.asyncio
    async def test_get_drift_alert_not_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_drift_alert.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/drift-alerts/nope"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_drift_alert_acknowledge(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        alert = _sample_drift_alert()
        mock_repo.get_drift_alert.return_value = alert
        mock_repo.upsert_drift_alert.return_value = alert

        resp = await client_with_mock_repo.patch(
            "/api/tenants/local-dev-tenant/drift-alerts/alert-001",
            json={"status": "acknowledged"},
        )
        assert resp.status_code == 200
        # Verify upsert was called
        mock_repo.upsert_drift_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_patch_drift_alert_not_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_drift_alert.return_value = None

        resp = await client_with_mock_repo.patch(
            "/api/tenants/local-dev-tenant/drift-alerts/nope",
            json={"status": "acknowledged"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_drift_detection(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        # Background task will call list_identities — configure mock
        mock_repo.list_identities.return_value = ([], 0)

        resp = await client_with_mock_repo.post(
            "/api/tenants/local-dev-tenant/drift-alerts/detect"
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"


# ---------------------------------------------------------------------------
# Baseline endpoint tests
# ---------------------------------------------------------------------------

class TestBaselineEndpoints:
    """Tests for the /baselines API routes."""

    @pytest.mark.asyncio
    async def test_get_baselines(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        baseline = _sample_baseline("Add user", mean=3.0, stddev=1.0)
        mock_repo.list_baselines.return_value = [baseline]

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/baselines/User_abc12345"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["baselines"][0]["action"] == "Add user"
