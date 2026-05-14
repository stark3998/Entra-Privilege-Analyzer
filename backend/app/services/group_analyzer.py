# backend/app/services/group_analyzer.py
"""Best-practice checks for Entra ID groups with role assignments."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.models.best_practice import (
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)
from app.models.group import GroupProfile

logger = logging.getLogger(__name__)

# Substring match for admin roles
_ADMIN_KEYWORD = "administrator"

# Patterns considered overly broad in dynamic membership rules
_BROAD_RULE_PATTERNS: list[str] = [
    "user.usertype",
    "user.accountenabled",
    "user.department -eq",
    "user.companyname",
]


class GroupAnalyzer:
    """Evaluates groups against security best practices and produces violations."""

    def evaluate_groups(
        self,
        tenant_id: str,
        groups: list[GroupProfile],
        role_assignments: dict[str, list[str]],
    ) -> list[BestPracticeViolation]:
        """Run all group checks and return violations.

        Parameters
        ----------
        tenant_id:
            The Azure tenant id.
        groups:
            Group profiles to evaluate.
        role_assignments:
            Mapping of group object_id to list of role names assigned to that group.
        """
        violations: list[BestPracticeViolation] = []

        for group in groups:
            # Merge role info from the explicit map into the profile's roles_assigned
            assigned_roles = role_assignments.get(group.id, []) or group.roles_assigned

            violations.extend(self._check_ownerless_role_group(tenant_id, group, assigned_roles))
            violations.extend(self._check_non_role_assignable_admin(tenant_id, group, assigned_roles))
            violations.extend(self._check_dynamic_admin(tenant_id, group, assigned_roles))
            violations.extend(self._check_broad_dynamic_rule(tenant_id, group))
            violations.extend(self._check_large_role_bearing(tenant_id, group, assigned_roles))

        return violations

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_ownerless_role_group(
        self,
        tenant_id: str,
        group: GroupProfile,
        assigned_roles: list[str],
    ) -> list[BestPracticeViolation]:
        """Ownerless group with roles -- no one accountable for membership."""
        if group.owner_count > 0 or not assigned_roles:
            return []

        return [
            _build_group_violation(
                tenant_id=tenant_id,
                group=group,
                violation_type=ViolationType.ROLE_ASSIGNABLE_GROUP,
                priority=ViolationPriority.HIGH,
                title=f"Ownerless group '{group.display_name}' has role assignments",
                description=(
                    f"Group '{group.display_name}' bears {len(assigned_roles)} role(s) "
                    "but has no owners. No one is accountable for membership changes."
                ),
                remediation_steps=[
                    "Assign at least one owner to this group.",
                    "Enable access reviews on the group membership.",
                ],
                affected_roles=assigned_roles,
                id_suffix="ownerless_roles",
            ),
        ]

    def _check_non_role_assignable_admin(
        self,
        tenant_id: str,
        group: GroupProfile,
        assigned_roles: list[str],
    ) -> list[BestPracticeViolation]:
        """Non-role-assignable group with admin roles."""
        if group.is_role_assignable:
            return []

        admin_roles = [r for r in assigned_roles if _ADMIN_KEYWORD in r.lower()]
        if not admin_roles:
            return []

        return [
            _build_group_violation(
                tenant_id=tenant_id,
                group=group,
                violation_type=ViolationType.ROLE_ASSIGNABLE_GROUP,
                priority=ViolationPriority.HIGH,
                title=f"Non-role-assignable group '{group.display_name}' has admin roles",
                description=(
                    f"Group '{group.display_name}' holds admin roles ({', '.join(admin_roles)}) "
                    "but is not marked as role-assignable. Any group owner can modify "
                    "membership, granting admin access to arbitrary users."
                ),
                remediation_steps=[
                    "Recreate the group as a role-assignable group (immutable after creation).",
                    "Restrict group ownership to privileged administrators.",
                ],
                affected_roles=admin_roles,
                id_suffix="non_ra_admin",
            ),
        ]

    def _check_dynamic_admin(
        self,
        tenant_id: str,
        group: GroupProfile,
        assigned_roles: list[str],
    ) -> list[BestPracticeViolation]:
        """Dynamic group with admin roles -- membership rule controls who gets admin."""
        if not group.is_dynamic:
            return []

        admin_roles = [r for r in assigned_roles if _ADMIN_KEYWORD in r.lower()]
        if not admin_roles:
            return []

        return [
            _build_group_violation(
                tenant_id=tenant_id,
                group=group,
                violation_type=ViolationType.ROLE_ASSIGNABLE_GROUP,
                priority=ViolationPriority.CRITICAL,
                title=f"Dynamic group '{group.display_name}' has admin roles",
                description=(
                    f"Group '{group.display_name}' is dynamic and holds admin roles "
                    f"({', '.join(admin_roles)}). A broad membership rule can grant "
                    "admin access to many users automatically."
                ),
                remediation_steps=[
                    "Replace the dynamic group with a static, role-assignable group.",
                    "If dynamic membership is required, tighten the membership rule.",
                    "Audit current members to verify they need admin access.",
                ],
                affected_roles=admin_roles,
                id_suffix="dynamic_admin",
            ),
        ]

    def _check_broad_dynamic_rule(
        self,
        tenant_id: str,
        group: GroupProfile,
    ) -> list[BestPracticeViolation]:
        """Dynamic group with overly broad membership rule."""
        if not group.is_dynamic or not group.membership_rule:
            return []

        rule_lower = group.membership_rule.lower()
        matched = [p for p in _BROAD_RULE_PATTERNS if p in rule_lower]
        if not matched:
            return []

        return [
            _build_group_violation(
                tenant_id=tenant_id,
                group=group,
                violation_type=ViolationType.ROLE_ASSIGNABLE_GROUP,
                priority=ViolationPriority.MEDIUM,
                title=f"Overly broad dynamic rule on group '{group.display_name}'",
                description=(
                    f"Group '{group.display_name}' uses a dynamic membership rule "
                    f"with broad patterns ({', '.join(matched)}). This may include "
                    "more members than intended."
                ),
                remediation_steps=[
                    "Narrow the membership rule to target specific attributes.",
                    "Review the current member list for unexpected inclusions.",
                ],
                affected_roles=group.roles_assigned,
                id_suffix="broad_dynamic",
            ),
        ]

    def _check_large_role_bearing(
        self,
        tenant_id: str,
        group: GroupProfile,
        assigned_roles: list[str],
    ) -> list[BestPracticeViolation]:
        """Large group (>50 transitive members) bearing role assignments."""
        if group.transitive_member_count <= 50 or not assigned_roles:
            return []

        return [
            _build_group_violation(
                tenant_id=tenant_id,
                group=group,
                violation_type=ViolationType.ROLE_ASSIGNABLE_GROUP,
                priority=ViolationPriority.MEDIUM,
                title=f"Large group '{group.display_name}' ({group.transitive_member_count} members) has role assignments",
                description=(
                    f"Group '{group.display_name}' has {group.transitive_member_count} "
                    f"transitive members and holds {len(assigned_roles)} role(s). "
                    "Large role-bearing groups increase blast radius if compromised."
                ),
                remediation_steps=[
                    "Consider splitting into smaller, scoped groups.",
                    "Review whether all members need the assigned roles.",
                    "Enable access reviews on the group.",
                ],
                affected_roles=assigned_roles,
                id_suffix="large_role_group",
            ),
        ]


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------


def _build_group_violation(
    *,
    tenant_id: str,
    group: GroupProfile,
    violation_type: ViolationType,
    priority: ViolationPriority,
    title: str,
    description: str,
    remediation_steps: list[str],
    affected_roles: list[str],
    id_suffix: str,
) -> BestPracticeViolation:
    """Construct a BestPracticeViolation for a group entity."""
    doc_id = f"group_{group.id}_{id_suffix}"
    return BestPracticeViolation(
        id=doc_id,
        tenant_id=tenant_id,
        identity_id=f"group_{group.id}",
        identity_display_name=group.display_name,
        identity_type="Group",
        violation_type=violation_type,
        priority=priority,
        title=title,
        description=description,
        remediation_steps=remediation_steps,
        affected_roles=affected_roles,
        detected_at=datetime.now(UTC),
    )
