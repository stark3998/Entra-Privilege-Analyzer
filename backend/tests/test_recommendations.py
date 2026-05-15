# backend/tests/test_recommendations.py
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.deps import CurrentUser, get_current_user
from app.config import Settings, get_settings
from app.data.builtin_roles import find_matching_entra_roles
from app.data.permission_catalog import action_to_permission, get_risk_weight
from app.models.export import ExportFormat
from app.models.identity import (
    CurrentRole,
    IdentityProfile,
    IdentityType,
    ObservedAction,
)
from app.models.role import RoleRecommendation, RoleScope
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.iac_exporter import IacExporter
from app.services.role_mapper import RoleMapper
from app.services.role_recommender import RoleRecommender

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
    actions: list[str] | None = None,
    roles: list[CurrentRole] | None = None,
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
        id="User_abc12345",
        tenant_id="test-tenant",
        identity_type=IdentityType.USER,
        object_id="abc12345",
        display_name="Test User",
        upn="test@contoso.com",
        current_roles=roles or [],
        observed_actions=observed,
        risk_score=0.0,
        action_count=len(observed),
        created_at=now,
        updated_at=now,
    )


def _sample_recommendation() -> RoleRecommendation:
    """Build a minimal RoleRecommendation for testing."""
    from app.models.role import CustomRoleDefinition

    now = datetime.now(UTC)
    return RoleRecommendation(
        id="User_abc12345",
        tenant_id="test-tenant",
        identity_id="User_abc12345",
        identity_display_name="Test User",
        identity_type="User",
        current_roles=[],
        required_permissions=["User.ReadWrite.All"],
        permission_gaps=[],
        best_builtin_match=None,
        alternative_builtins=[],
        custom_role=CustomRoleDefinition(
            name="Custom-User-abc12345",
            description="Least-privilege custom role for Test User based on observed actions",
            scope=RoleScope.ENTRA,
            permissions=["User.ReadWrite.All"],
            is_assignable_scopes=["/"],
        ),
        reduction_score=0.0,
        computed_at=now,
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
# Permission catalog tests
# ---------------------------------------------------------------------------


class TestPermissionCatalog:
    """Tests for action_to_permission mapping."""

    def test_known_action_maps(self) -> None:
        assert action_to_permission("Add user") == "User.ReadWrite.All"

    def test_unknown_action_returns_none(self) -> None:
        assert action_to_permission("Some unknown action") is None

    def test_role_management_action(self) -> None:
        assert action_to_permission("Add member to role") == "RoleManagement.ReadWrite.Directory"

    def test_risk_weight_known(self) -> None:
        assert get_risk_weight("User.ReadWrite.All") == "high"

    def test_risk_weight_unknown_defaults_low(self) -> None:
        assert get_risk_weight("NonExistent.Permission") == "low"


# ---------------------------------------------------------------------------
# Built-in role matching tests
# ---------------------------------------------------------------------------


class TestBuiltInRoleMatching:
    """Tests for find_matching_entra_roles."""

    def test_exact_permission_match(self) -> None:
        """Helpdesk Administrator has microsoft.directory/users/password/update."""
        matches = find_matching_entra_roles({"microsoft.directory/users/password/update"})
        # Helpdesk Admin should appear with a positive score
        helpdesk = [m for m in matches if m.role_name == "Helpdesk Administrator"]
        assert len(helpdesk) == 1
        assert helpdesk[0].match_score > 0

    def test_wildcard_match_covers_specific(self) -> None:
        """User Administrator (microsoft.directory/users/allProperties/allTasks) should
        cover microsoft.directory/users/password/update."""
        matches = find_matching_entra_roles({"microsoft.directory/users/password/update"})
        user_admin = [m for m in matches if m.role_name == "User Administrator"]
        assert len(user_admin) == 1
        assert user_admin[0].match_score > 0

    def test_global_admin_covers_everything(self) -> None:
        """Global Administrator (microsoft.directory/*/allTasks) should match any
        microsoft.directory permission."""
        matches = find_matching_entra_roles({"microsoft.directory/users/password/update"})
        ga = [m for m in matches if m.role_name == "Global Administrator"]
        assert len(ga) == 1
        assert ga[0].match_score > 0

    def test_no_permissions_gives_zero_scores(self) -> None:
        """An empty required set should produce 0 scores for all roles."""
        matches = find_matching_entra_roles(set())
        # match_score = 0 / max(0, 1) = 0 for all
        for m in matches:
            assert m.match_score == 0.0

    def test_results_sorted_by_score_desc(self) -> None:
        matches = find_matching_entra_roles({"microsoft.directory/users/password/update"})
        scores = [m.match_score for m in matches]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# RoleMapper tests
# ---------------------------------------------------------------------------


class TestRoleMapper:
    """Tests for RoleMapper.map_identity_permissions."""

    def test_maps_observed_actions_to_permissions(self) -> None:
        profile = _sample_profile(actions=["Add user", "Delete user"])
        mapper = RoleMapper()
        required, gaps = mapper.map_identity_permissions(profile)
        assert "User.ReadWrite.All" in required

    def test_unknown_actions_not_in_required(self) -> None:
        profile = _sample_profile(actions=["Sign-in"])
        mapper = RoleMapper()
        required, gaps = mapper.map_identity_permissions(profile)
        # "Sign-in" is not in audit_operation_to_permission
        assert len(required) == 0

    def test_gaps_include_unused_roles(self) -> None:
        profile = _sample_profile(
            actions=["Add user"],
            roles=[
                CurrentRole(
                    role_id="r1",
                    role_name="User.ReadWrite.All",
                    scope="/",
                ),
                CurrentRole(
                    role_id="r2",
                    role_name="Directory.ReadWrite.All",
                    scope="/",
                ),
            ],
        )
        mapper = RoleMapper()
        required, gaps = mapper.map_identity_permissions(profile)
        assert "User.ReadWrite.All" in required
        gap_perms = [g.permission for g in gaps]
        assert "Directory.ReadWrite.All" in gap_perms

    def test_no_gaps_when_all_used(self) -> None:
        profile = _sample_profile(
            actions=["Add user"],
            roles=[
                CurrentRole(
                    role_id="r1",
                    role_name="User.ReadWrite.All",
                    scope="/",
                ),
            ],
        )
        mapper = RoleMapper()
        required, gaps = mapper.map_identity_permissions(profile)
        assert len(gaps) == 0


# ---------------------------------------------------------------------------
# IaC exporter tests
# ---------------------------------------------------------------------------


class TestIacExporter:
    """Tests for IacExporter output."""

    def test_terraform_entra_contains_resource(self) -> None:
        rec = _sample_recommendation()
        exporter = IacExporter()
        result = exporter.export_terraform(rec)
        assert "azuread_custom_directory_role" in result.content
        assert result.filename.endswith(".tf")

    def test_terraform_azure_contains_resource(self) -> None:
        rec = _sample_recommendation()
        rec.custom_role.scope = RoleScope.AZURE
        exporter = IacExporter()
        result = exporter.export_terraform(rec)
        assert "azurerm_role_definition" in result.content

    def test_bicep_contains_resource(self) -> None:
        rec = _sample_recommendation()
        exporter = IacExporter()
        result = exporter.export_bicep(rec)
        assert "Microsoft.Authorization/roleDefinitions" in result.content
        assert result.filename.endswith(".bicep")

    def test_arm_is_valid_json(self) -> None:
        rec = _sample_recommendation()
        exporter = IacExporter()
        result = exporter.export_arm(rec)
        parsed = json.loads(result.content)
        assert "$schema" in parsed
        assert len(parsed["resources"]) == 1
        assert result.filename.endswith(".json")

    def test_export_dispatch(self) -> None:
        rec = _sample_recommendation()
        exporter = IacExporter()
        for fmt in ExportFormat:
            result = exporter.export(rec, fmt)
            assert result.format == fmt
            assert len(result.content) > 0


# ---------------------------------------------------------------------------
# RoleRecommender integration test
# ---------------------------------------------------------------------------


class TestRoleRecommender:
    """Integration test for RoleRecommender.compute_recommendation."""

    def test_full_recommendation(self) -> None:
        profile = _sample_profile(
            actions=["Add user", "Add member to group"],
            roles=[
                CurrentRole(role_id="r1", role_name="User.ReadWrite.All", scope="/"),
                CurrentRole(role_id="r2", role_name="Directory.ReadWrite.All", scope="/"),
                CurrentRole(
                    role_id="r3", role_name="RoleManagement.ReadWrite.Directory", scope="/"
                ),
            ],
        )
        mapper = RoleMapper()
        recommender = RoleRecommender(mapper)
        rec = recommender.compute_recommendation(profile)

        assert rec.identity_id == "User_abc12345"
        assert "User.ReadWrite.All" in rec.required_permissions
        assert "Group.ReadWrite.All" in rec.required_permissions
        assert rec.custom_role.name == "Custom-User-abc12345"
        assert rec.reduction_score > 0
        assert rec.computed_at is not None


# ---------------------------------------------------------------------------
# Recommendation endpoint tests
# ---------------------------------------------------------------------------


class TestRecommendationEndpoints:
    """Tests for the /recommendations API routes."""

    @pytest.mark.asyncio
    async def test_list_recommendations(
        self,
        client_with_mock_repo: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        rec = _sample_recommendation()
        mock_repo.list_recommendations.return_value = ([rec], 1)

        resp = await client_with_mock_repo.get("/api/tenants/local-dev-tenant/recommendations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["identity_id"] == "User_abc12345"

    @pytest.mark.asyncio
    async def test_get_recommendation_found(
        self,
        client_with_mock_repo: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        rec = _sample_recommendation()
        mock_repo.get_recommendation.return_value = rec

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/recommendations/User_abc12345"
        )
        assert resp.status_code == 200
        assert resp.json()["identity_id"] == "User_abc12345"

    @pytest.mark.asyncio
    async def test_get_recommendation_not_found(
        self,
        client_with_mock_repo: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_recommendation.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/recommendations/User_nope"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_terraform(
        self,
        client_with_mock_repo: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        rec = _sample_recommendation()
        mock_repo.get_recommendation.return_value = rec

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/exports/User_abc12345?format=terraform"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["format"] == "terraform"
        assert "azuread_custom_directory_role" in body["content"]

    @pytest.mark.asyncio
    async def test_export_not_found(
        self,
        client_with_mock_repo: AsyncClient,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_recommendation.return_value = None

        resp = await client_with_mock_repo.get(
            "/api/tenants/local-dev-tenant/exports/User_nope?format=terraform"
        )
        assert resp.status_code == 404
