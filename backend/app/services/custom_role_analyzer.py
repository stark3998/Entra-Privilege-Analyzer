# backend/app/services/custom_role_analyzer.py
"""Best-practice checks for Entra ID / Azure RBAC custom role definitions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.models.best_practice import (
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)
from app.models.custom_role import CustomRoleProfile

logger = logging.getLogger(__name__)

# Wildcard patterns that signal overprivilege
_WILDCARD_PATTERNS: list[str] = [
    "*/alltasks",
    "allproperties/alltasks",
]

# Permission actions that create escalation paths
_ESCALATION_PERMISSIONS: list[str] = [
    "roleassignments/allproperties/alltasks",
    "applications/credentials/update",
    "serviceprincipals/credentials/update",
]

# Threshold: too many custom roles indicates sprawl
_SPRAWL_THRESHOLD = 20


class CustomRoleAnalyzer:
    """Evaluates custom role definitions against best practices and produces violations."""

    def evaluate_custom_roles(
        self,
        tenant_id: str,
        roles: list[CustomRoleProfile],
    ) -> list[BestPracticeViolation]:
        """Run all custom-role checks and return violations.

        Parameters
        ----------
        tenant_id:
            The Azure tenant id.
        roles:
            Custom role profiles to evaluate.
        """
        violations: list[BestPracticeViolation] = []

        for role in roles:
            violations.extend(self._check_wildcard_permissions(tenant_id, role))
            violations.extend(self._check_equivalent_builtin(tenant_id, role))
            violations.extend(self._check_unused(tenant_id, role))
            violations.extend(self._check_escalation_permissions(tenant_id, role))
            violations.extend(self._check_no_description(tenant_id, role))

        violations.extend(self._check_sprawl(tenant_id, roles))

        return violations

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_wildcard_permissions(
        self,
        tenant_id: str,
        role: CustomRoleProfile,
    ) -> list[BestPracticeViolation]:
        """Overprivileged: permissions contain wildcard allTasks patterns."""
        perms_lower = [p.lower() for p in role.permissions]
        matched = [p for p in _WILDCARD_PATTERNS if any(p in perm for perm in perms_lower)]
        if not matched:
            return []

        return [
            _build_role_violation(
                tenant_id=tenant_id,
                role=role,
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=ViolationPriority.CRITICAL,
                title=f"Custom role '{role.display_name}' uses wildcard permissions",
                description=(
                    f"Role '{role.display_name}' contains wildcard permission patterns "
                    f"({', '.join(matched)}). This grants far more access than needed."
                ),
                remediation_steps=[
                    "Replace wildcard permissions with specific action grants.",
                    "Audit all actions this role actually needs.",
                ],
                id_suffix="wildcard",
            ),
        ]

    def _check_equivalent_builtin(
        self,
        tenant_id: str,
        role: CustomRoleProfile,
    ) -> list[BestPracticeViolation]:
        """Equivalent to built-in: overlap >= 90% with a built-in role."""
        high_overlap = [o for o in role.overlap_with_builtin if o.overlap_pct >= 0.9]
        if not high_overlap:
            return []

        top = high_overlap[0]
        return [
            _build_role_violation(
                tenant_id=tenant_id,
                role=role,
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=ViolationPriority.MEDIUM,
                title=f"Custom role '{role.display_name}' duplicates built-in '{top.role_name}'",
                description=(
                    f"Role '{role.display_name}' has {top.overlap_pct:.0%} overlap with "
                    f"built-in role '{top.role_name}'. Use the built-in role instead to "
                    "reduce management overhead."
                ),
                remediation_steps=[
                    f"Migrate assignments to built-in role '{top.role_name}'.",
                    "Delete the custom role after migration.",
                ],
                id_suffix="equiv_builtin",
            ),
        ]

    def _check_unused(
        self,
        tenant_id: str,
        role: CustomRoleProfile,
    ) -> list[BestPracticeViolation]:
        """Unused: custom role has zero assignments."""
        if role.assignment_count > 0:
            return []

        return [
            _build_role_violation(
                tenant_id=tenant_id,
                role=role,
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=ViolationPriority.MEDIUM,
                title=f"Custom role '{role.display_name}' has no assignments",
                description=(
                    f"Role '{role.display_name}' is not assigned to any identity. "
                    "Unused custom roles add clutter and should be cleaned up."
                ),
                remediation_steps=[
                    "Verify the role is no longer needed.",
                    "Delete the custom role definition.",
                ],
                id_suffix="unused",
            ),
        ]

    def _check_escalation_permissions(
        self,
        tenant_id: str,
        role: CustomRoleProfile,
    ) -> list[BestPracticeViolation]:
        """Critical permissions: role contains actions that enable privilege escalation."""
        perms_lower = [p.lower() for p in role.permissions]
        matched = [ep for ep in _ESCALATION_PERMISSIONS if any(ep in perm for perm in perms_lower)]
        if not matched:
            return []

        return [
            _build_role_violation(
                tenant_id=tenant_id,
                role=role,
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=ViolationPriority.CRITICAL,
                title=f"Custom role '{role.display_name}' has escalation-path permissions",
                description=(
                    f"Role '{role.display_name}' includes permissions that enable "
                    f"privilege escalation ({', '.join(matched)}). An attacker with "
                    "this role could elevate to higher privileges."
                ),
                remediation_steps=[
                    "Remove escalation-path permissions unless absolutely required.",
                    "Restrict this role to a narrow scope (e.g., specific resource group).",
                    "Require PIM activation with approval for this role.",
                ],
                id_suffix="escalation",
            ),
        ]

    def _check_no_description(
        self,
        tenant_id: str,
        role: CustomRoleProfile,
    ) -> list[BestPracticeViolation]:
        """No description: custom role lacks documentation."""
        if role.description.strip():
            return []

        return [
            _build_role_violation(
                tenant_id=tenant_id,
                role=role,
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=ViolationPriority.LOW,
                title=f"Custom role '{role.display_name}' has no description",
                description=(
                    f"Role '{role.display_name}' has an empty description. "
                    "Documenting the role's purpose aids auditing and governance."
                ),
                remediation_steps=[
                    "Add a description explaining the role's intended use case.",
                ],
                id_suffix="no_desc",
            ),
        ]

    def _check_sprawl(
        self,
        tenant_id: str,
        roles: list[CustomRoleProfile],
    ) -> list[BestPracticeViolation]:
        """Sprawl: tenant has too many custom roles."""
        if len(roles) <= _SPRAWL_THRESHOLD:
            return []

        return [
            BestPracticeViolation(
                id=f"tenant_{tenant_id}_custom_role_sprawl",
                tenant_id=tenant_id,
                identity_id=f"tenant_{tenant_id}",
                identity_display_name="Tenant",
                identity_type="Tenant",
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=ViolationPriority.MEDIUM,
                title=f"Custom role sprawl: {len(roles)} custom roles defined",
                description=(
                    f"The tenant has {len(roles)} custom roles (threshold: "
                    f"{_SPRAWL_THRESHOLD}). Excessive custom roles increase "
                    "management complexity and audit burden."
                ),
                remediation_steps=[
                    "Consolidate overlapping custom roles.",
                    "Migrate to built-in roles where possible.",
                    "Delete unused custom role definitions.",
                ],
                affected_roles=[r.display_name for r in roles],
                detected_at=datetime.now(UTC),
            ),
        ]


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------


def _build_role_violation(
    *,
    tenant_id: str,
    role: CustomRoleProfile,
    violation_type: ViolationType,
    priority: ViolationPriority,
    title: str,
    description: str,
    remediation_steps: list[str],
    id_suffix: str,
) -> BestPracticeViolation:
    """Construct a BestPracticeViolation for a custom role entity."""
    doc_id = f"customrole_{role.role_definition_id}_{id_suffix}"
    return BestPracticeViolation(
        id=doc_id,
        tenant_id=tenant_id,
        identity_id=f"customrole_{role.role_definition_id}",
        identity_display_name=role.display_name,
        identity_type="CustomRole",
        violation_type=violation_type,
        priority=priority,
        title=title,
        description=description,
        remediation_steps=remediation_steps,
        affected_roles=[],
        detected_at=datetime.now(UTC),
    )
