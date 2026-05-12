# backend/tests/test_best_practices.py
"""Tests for Phase 5: Best Practice Advisor."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.models.best_practice import (
    BestPracticeSummary,
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)
from app.models.identity import (
    CurrentRole,
    IdentityProfile,
    IdentityType,
    ObservedAction,
)
from app.models.role import RoleRecommendation, RoleScope
from app.services.best_practice_analyzer import BestPracticeAnalyzer
from app.services.cosmos import CosmosRepo, get_cosmos_repo


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
    identity_id: str = "User_abc12345",
    display_name: str = "Test User",
    actions: list[str] | None = None,
    roles: list[CurrentRole] | None = None,
    last_seen: datetime | None = None,
    identity_type: IdentityType = IdentityType.USER,
) -> IdentityProfile:
    """Build a minimal IdentityProfile for testing."""
    now = datetime.now(UTC)
    observed = [
        ObservedAction(
            action=a,
            resource="test-resource",
            count=1,
            first_seen=now,
            last_seen=now,
        )
        for a in (actions or [])
    ]
    return IdentityProfile(
        id=identity_id,
        tenant_id="test-tenant",
        identity_type=identity_type,
        object_id="abc12345",
        display_name=display_name,
        upn="test@contoso.com",
        current_roles=roles or [],
        observed_actions=observed,
        risk_score=0.0,
        action_count=len(observed),
        last_seen=last_seen or now,
        first_seen=now,
        created_at=now,
        updated_at=now,
    )


def _sample_recommendation(reduction_score: float = 60.0) -> RoleRecommendation:
    from app.models.role import CustomRoleDefinition, PermissionGap

    now = datetime.now(UTC)
    return RoleRecommendation(
        id="User_abc12345",
        tenant_id="test-tenant",
        identity_id="User_abc12345",
        identity_display_name="Test User",
        identity_type="User",
        current_roles=[],
        required_permissions=["User.ReadWrite.All"],
        permission_gaps=[
            PermissionGap(permission="Directory.ReadWrite.All", risk_weight="high", is_used=False),
        ],
        best_builtin_match=None,
        alternative_builtins=[],
        custom_role=CustomRoleDefinition(
            name="Custom-User-abc12345",
            description="Least-privilege custom role",
            scope=RoleScope.ENTRA,
            permissions=["User.ReadWrite.All"],
            is_assignable_scopes=["/"],
        ),
        reduction_score=reduction_score,
        computed_at=now,
    )


def _sample_violation(
    *,
    violation_type: ViolationType = ViolationType.STALE_IDENTITY,
    priority: ViolationPriority = ViolationPriority.HIGH,
) -> BestPracticeViolation:
    return BestPracticeViolation(
        id="User_abc12345_stale_identity",
        tenant_id="test-tenant",
        identity_id="User_abc12345",
        identity_display_name="Test User",
        identity_type="User",
        violation_type=violation_type,
        priority=priority,
        title="Stale identity",
        description="Test violation",
        remediation_steps=["Fix it"],
        affected_roles=["Global Administrator"],
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
# Stale identity detection tests
# ---------------------------------------------------------------------------

class TestStaleIdentityDetection:
    """Tests for stale identity rule at various thresholds."""

    @pytest.mark.asyncio
    async def test_active_identity_no_violation(self, mock_repo: AsyncMock) -> None:
        """Identity active within 30 days should not trigger violation."""
        profile = _sample_profile(last_seen=datetime.now(UTC) - timedelta(days=10))
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        stale = [v for v in violations if v.violation_type == ViolationType.STALE_IDENTITY]
        assert len(stale) == 0

    @pytest.mark.asyncio
    async def test_31_days_stale_low_priority(self, mock_repo: AsyncMock) -> None:
        """31 days inactive should produce a low-priority stale violation."""
        profile = _sample_profile(last_seen=datetime.now(UTC) - timedelta(days=31))
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        stale = [v for v in violations if v.violation_type == ViolationType.STALE_IDENTITY]
        assert len(stale) == 1
        assert stale[0].priority == ViolationPriority.LOW

    @pytest.mark.asyncio
    async def test_61_days_stale_medium_priority(self, mock_repo: AsyncMock) -> None:
        """61 days inactive should produce a medium-priority stale violation."""
        profile = _sample_profile(last_seen=datetime.now(UTC) - timedelta(days=61))
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        stale = [v for v in violations if v.violation_type == ViolationType.STALE_IDENTITY]
        assert len(stale) == 1
        assert stale[0].priority == ViolationPriority.MEDIUM

    @pytest.mark.asyncio
    async def test_91_days_stale_high_priority(self, mock_repo: AsyncMock) -> None:
        """91 days inactive should produce a high-priority stale violation."""
        profile = _sample_profile(last_seen=datetime.now(UTC) - timedelta(days=91))
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        stale = [v for v in violations if v.violation_type == ViolationType.STALE_IDENTITY]
        assert len(stale) == 1
        assert stale[0].priority == ViolationPriority.HIGH

    @pytest.mark.asyncio
    async def test_never_seen_identity(self, mock_repo: AsyncMock) -> None:
        """Identity with last_seen=None should produce a high violation."""
        profile = _sample_profile()
        profile.last_seen = None
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        stale = [v for v in violations if v.violation_type == ViolationType.STALE_IDENTITY]
        assert len(stale) == 1
        assert stale[0].priority == ViolationPriority.HIGH


# ---------------------------------------------------------------------------
# Permanent admin detection tests
# ---------------------------------------------------------------------------

class TestPermanentAdminDetection:
    """Tests for permanent admin role violation."""

    @pytest.mark.asyncio
    async def test_permanent_global_admin_critical(self, mock_repo: AsyncMock) -> None:
        """Permanent Global Administrator should produce a critical violation."""
        profile = _sample_profile(
            roles=[
                CurrentRole(
                    role_id="ga",
                    role_name="Global Administrator",
                    scope="/",
                    is_permanent=True,
                ),
            ],
        )
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        admin_violations = [
            v for v in violations if v.violation_type == ViolationType.PERMANENT_ADMIN
        ]
        assert len(admin_violations) == 1
        assert admin_violations[0].priority == ViolationPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_permanent_other_admin_high(self, mock_repo: AsyncMock) -> None:
        """Permanent User Administrator should produce a high violation."""
        profile = _sample_profile(
            roles=[
                CurrentRole(
                    role_id="ua",
                    role_name="User Administrator",
                    scope="/",
                    is_permanent=True,
                ),
            ],
        )
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        admin_violations = [
            v for v in violations if v.violation_type == ViolationType.PERMANENT_ADMIN
        ]
        assert len(admin_violations) == 1
        assert admin_violations[0].priority == ViolationPriority.HIGH

    @pytest.mark.asyncio
    async def test_non_permanent_admin_no_violation(self, mock_repo: AsyncMock) -> None:
        """Non-permanent admin role should not trigger violation."""
        profile = _sample_profile(
            roles=[
                CurrentRole(
                    role_id="ga",
                    role_name="Global Administrator",
                    scope="/",
                    is_permanent=False,
                    assignment_type="pim",
                ),
            ],
        )
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        admin_violations = [
            v for v in violations if v.violation_type == ViolationType.PERMANENT_ADMIN
        ]
        assert len(admin_violations) == 0


# ---------------------------------------------------------------------------
# Separation of duties tests
# ---------------------------------------------------------------------------

class TestSeparationOfDuties:
    """Tests for separation of duties violation."""

    @pytest.mark.asyncio
    async def test_conflicting_roles_detected(self, mock_repo: AsyncMock) -> None:
        """Holding both User Admin and Application Admin should trigger SoD."""
        profile = _sample_profile(
            roles=[
                CurrentRole(role_id="ua", role_name="User Administrator", scope="/"),
                CurrentRole(role_id="aa", role_name="Application Administrator", scope="/"),
            ],
        )
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        sod = [v for v in violations if v.violation_type == ViolationType.SEPARATION_OF_DUTIES]
        assert len(sod) == 1
        assert sod[0].priority == ViolationPriority.HIGH

    @pytest.mark.asyncio
    async def test_no_conflict_no_violation(self, mock_repo: AsyncMock) -> None:
        """Non-conflicting role pairs should not trigger SoD."""
        profile = _sample_profile(
            roles=[
                CurrentRole(role_id="ua", role_name="User Administrator", scope="/"),
                CurrentRole(role_id="ha", role_name="Helpdesk Administrator", scope="/"),
            ],
        )
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations = await analyzer.evaluate_identity("test-tenant", profile)

        sod = [v for v in violations if v.violation_type == ViolationType.SEPARATION_OF_DUTIES]
        assert len(sod) == 0


# ---------------------------------------------------------------------------
# Compliance score calculation tests
# ---------------------------------------------------------------------------

class TestComplianceScore:
    """Tests for compliance_score in BestPracticeSummary."""

    @pytest.mark.asyncio
    async def test_perfect_compliance(self, mock_repo: AsyncMock) -> None:
        """No violations -> compliance_score = 100."""
        # Empty tenant — no identities
        mock_repo.list_identities.return_value = ([], 0)

        analyzer = BestPracticeAnalyzer(mock_repo)
        _violations, summary = await analyzer.evaluate_tenant("test-tenant")

        assert summary.compliance_score == 100.0
        assert summary.total_violations == 0

    @pytest.mark.asyncio
    async def test_critical_violations_reduce_score(self, mock_repo: AsyncMock) -> None:
        """Critical violations should heavily reduce compliance score."""
        # One identity with permanent Global Admin
        profile = _sample_profile(
            roles=[
                CurrentRole(
                    role_id="ga",
                    role_name="Global Administrator",
                    scope="/",
                    is_permanent=True,
                ),
            ],
        )
        mock_repo.list_identities.return_value = ([profile], 1)
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        violations, summary = await analyzer.evaluate_tenant("test-tenant")

        # Should have at least the permanent_admin critical violation
        assert summary.total_violations > 0
        assert summary.compliance_score < 100.0

    @pytest.mark.asyncio
    async def test_score_floor_at_zero(self, mock_repo: AsyncMock) -> None:
        """Score should never go below 0."""
        # Multiple identities with lots of violations
        profiles = []
        for i in range(10):
            p = _sample_profile(
                identity_id=f"User_{i}",
                display_name=f"User {i}",
                roles=[
                    CurrentRole(
                        role_id="ga",
                        role_name="Global Administrator",
                        scope="/",
                        is_permanent=True,
                    ),
                    CurrentRole(
                        role_id="ua",
                        role_name="User Administrator",
                        scope="/",
                        is_permanent=True,
                    ),
                    CurrentRole(
                        role_id="aa",
                        role_name="Application Administrator",
                        scope="/",
                        is_permanent=True,
                    ),
                ],
                last_seen=datetime.now(UTC) - timedelta(days=120),
            )
            profiles.append(p)

        mock_repo.list_identities.return_value = (profiles, len(profiles))
        mock_repo.get_recommendation.return_value = None

        analyzer = BestPracticeAnalyzer(mock_repo)
        _violations, summary = await analyzer.evaluate_tenant("test-tenant")

        assert summary.compliance_score >= 0.0


# ---------------------------------------------------------------------------
# Best practices endpoint tests
# ---------------------------------------------------------------------------

class TestBestPracticesEndpoints:
    """Tests for the /best-practices API routes."""

    @pytest.mark.asyncio
    async def test_list_violations(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        violation = _sample_violation()
        mock_repo.list_violations.return_value = ([violation], 1)

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/best-practices"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["violation_type"] == "stale_identity"

    @pytest.mark.asyncio
    async def test_list_violations_with_filter(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        violation = _sample_violation(violation_type=ViolationType.PERMANENT_ADMIN)
        mock_repo.list_violations.return_value = ([violation], 1)

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/best-practices?type=permanent_admin"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    @pytest.mark.asyncio
    async def test_get_violation_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        violation = _sample_violation()
        mock_repo.get_violation.return_value = violation

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/best-practices/User_abc12345_stale_identity"
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == "User_abc12345_stale_identity"

    @pytest.mark.asyncio
    async def test_get_violation_not_found(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_violation.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/best-practices/nope"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_trigger_evaluation(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        # Background task will call list_identities and upsert_violation
        mock_repo.list_identities.return_value = ([], 0)

        resp = await client_with_mock_repo.post(
            "/api/tenants/local-dev-tenant/best-practices/evaluate"
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_compliance_summary(
        self, client_with_mock_repo: AsyncClient, mock_repo: AsyncMock,
    ) -> None:
        """Summary endpoint should return a live evaluation."""
        # No identities -> perfect compliance
        mock_repo.list_identities.return_value = ([], 0)

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/best-practices/summary"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["compliance_score"] == 100.0
        assert body["total_violations"] == 0
