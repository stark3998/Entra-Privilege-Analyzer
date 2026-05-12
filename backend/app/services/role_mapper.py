# backend/app/services/role_mapper.py
"""Maps observed actions to required permissions and identifies overprivilege gaps."""
from __future__ import annotations

import logging

from app.data.permission_catalog import action_to_permission, get_risk_weight
from app.models.identity import IdentityProfile
from app.models.role import PermissionGap

logger = logging.getLogger(__name__)


class RoleMapper:
    """Translates an identity's observed actions into permission requirements."""

    def map_identity_permissions(
        self, profile: IdentityProfile
    ) -> tuple[set[str], list[PermissionGap]]:
        """Determine required permissions and identify unused (gap) permissions.

        Returns:
            A tuple of (required_permissions, permission_gaps).
            ``required_permissions`` — the minimum set of permissions needed.
            ``permission_gaps`` — permissions held via current roles but never
            observed in use (overprivilege indicators).
        """
        # Collect permissions that the identity actually used
        required: set[str] = set()
        for observed in profile.observed_actions:
            perm = action_to_permission(observed.action)
            if perm is not None:
                required.add(perm)

        # Collect all permissions implied by current role names.
        # Current roles store a role_name (e.g. "User.ReadWrite.All") which
        # may itself be a Graph permission, or a high-level role name.
        # We treat each role_name as a permission label for gap analysis.
        current_permission_labels: set[str] = set()
        for role in profile.current_roles:
            current_permission_labels.add(role.role_name)

        # Gaps: permissions held but NOT in the required set
        gaps: list[PermissionGap] = []
        for perm_label in sorted(current_permission_labels):
            is_used = perm_label in required
            if not is_used:
                gaps.append(
                    PermissionGap(
                        permission=perm_label,
                        risk_weight=get_risk_weight(perm_label),
                        is_used=False,
                    )
                )

        return required, gaps
