# backend/app/services/role_recommender.py
"""Main recommendation engine — computes least-privilege role recommendations."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.data.builtin_roles import find_matching_azure_roles, find_matching_entra_roles
from app.models.identity import IdentityProfile
from app.models.role import (
    BuiltInRoleMatch,
    CustomRoleDefinition,
    RoleRecommendation,
    RoleScope,
)
from app.services.role_mapper import RoleMapper

logger = logging.getLogger(__name__)

_MAX_ALTERNATIVES = 3


class RoleRecommender:
    """Computes a full role recommendation for a single identity."""

    def __init__(self, mapper: RoleMapper) -> None:
        self._mapper = mapper

    def compute_recommendation(self, profile: IdentityProfile) -> RoleRecommendation:
        """Analyse an identity and return a complete ``RoleRecommendation``.

        Steps:
        1. Map observed actions to required permissions.
        2. Compute permission gaps (unused privileges).
        3. Find the best built-in role match.
        4. Generate a minimal custom role definition.
        5. Compute the reduction score.
        """
        required_permissions, gaps = self._mapper.map_identity_permissions(profile)

        # Determine scope heuristic: if any current role scope starts with "/"
        # we treat it as Azure RBAC, otherwise Entra.
        has_azure_scope = any(
            role.scope.startswith("/subscriptions") for role in profile.current_roles
        )
        scope = RoleScope.AZURE if has_azure_scope else RoleScope.ENTRA

        # Find built-in matches
        if scope == RoleScope.AZURE:
            matches = find_matching_azure_roles(required_permissions)
        else:
            matches = find_matching_entra_roles(required_permissions)

        best_match: BuiltInRoleMatch | None = matches[0] if matches else None
        alternatives: list[BuiltInRoleMatch] = matches[1 : _MAX_ALTERNATIVES + 1]

        # Generate custom role definition with exactly the required permissions
        object_id_prefix = profile.object_id[:8]
        custom_role = CustomRoleDefinition(
            name=f"Custom-{profile.identity_type.value}-{object_id_prefix}",
            description=(
                f"Least-privilege custom role for {profile.display_name} "
                f"based on observed actions"
            ),
            scope=scope,
            permissions=sorted(required_permissions),
            is_assignable_scopes=["/"],
        )

        # Reduction score: % of current permissions that are unused
        total_current = len(profile.current_roles)
        total_gaps = len(gaps)
        reduction_score = (total_gaps / max(total_current, 1)) * 100
        reduction_score = min(reduction_score, 100.0)

        return RoleRecommendation(
            id=profile.id,
            tenant_id=profile.tenant_id,
            identity_id=profile.id,
            identity_display_name=profile.display_name,
            identity_type=profile.identity_type.value,
            current_roles=profile.current_roles,
            required_permissions=sorted(required_permissions),
            permission_gaps=gaps,
            best_builtin_match=best_match,
            alternative_builtins=alternatives,
            custom_role=custom_role,
            reduction_score=round(reduction_score, 2),
            computed_at=datetime.now(UTC),
        )
