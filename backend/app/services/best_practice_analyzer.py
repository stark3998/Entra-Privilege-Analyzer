# backend/app/services/best_practice_analyzer.py
"""Rule engine that evaluates identities against Entra ID / Azure RBAC best practices."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.models.best_practice import (
    BestPracticeSummary,
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)
from app.models.identity import IdentityProfile, IdentityType
from app.services.cosmos import CosmosRepo

logger = logging.getLogger(__name__)

# Role name pairs that violate separation of duties
_SOD_CONFLICTS: list[tuple[str, str]] = [
    ("User Administrator", "Application Administrator"),
    ("Global Administrator", "Security Administrator"),
    ("Privileged Role Administrator", "Helpdesk Administrator"),
    ("Exchange Administrator", "SharePoint Administrator"),
]

# Priority weights for compliance score calculation
_PRIORITY_WEIGHTS: dict[str, int] = {
    "critical": 20,
    "high": 10,
    "medium": 5,
    "low": 1,
    "info": 0,
}


class BestPracticeAnalyzer:
    """Evaluates identities against best practice rules and generates violations."""

    def __init__(self, repo: CosmosRepo) -> None:
        self._repo = repo

    async def evaluate_identity(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """Run all best practice rules against a single identity."""
        violations: list[BestPracticeViolation] = []

        violations.extend(self._check_stale_identity(tenant_id, identity))
        violations.extend(self._check_permanent_admin(tenant_id, identity))
        violations.extend(self._check_no_pim(tenant_id, identity))
        violations.extend(await self._check_overprivileged(tenant_id, identity))
        violations.extend(self._check_separation_of_duties(tenant_id, identity))
        violations.extend(self._check_role_assignable_group(tenant_id, identity))

        return violations

    async def evaluate_tenant(
        self,
        tenant_id: str,
    ) -> tuple[list[BestPracticeViolation], BestPracticeSummary]:
        """Evaluate all identities in a tenant and compute compliance summary."""
        now = datetime.now(UTC)
        all_violations: list[BestPracticeViolation] = []

        # Paginate through all identities
        offset = 0
        page_size = 100
        while True:
            items, total = await self._repo.list_identities(
                tenant_id=tenant_id, offset=offset, limit=page_size,
            )
            for identity in items:
                try:
                    violations = await self.evaluate_identity(tenant_id, identity)
                    all_violations.extend(violations)
                except Exception:
                    logger.exception(
                        "Failed to evaluate identity %s/%s",
                        tenant_id,
                        identity.id,
                    )

            if offset + page_size >= total:
                break
            offset += page_size

        # Compute summary
        by_priority: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for v in all_violations:
            by_priority[v.priority.value] = by_priority.get(v.priority.value, 0) + 1
            by_type[v.violation_type.value] = by_type.get(v.violation_type.value, 0) + 1

        # compliance_score = max(0, 100 - weighted penalty)
        penalty = sum(
            count * _PRIORITY_WEIGHTS.get(prio, 0)
            for prio, count in by_priority.items()
        )
        compliance_score = max(0.0, 100.0 - penalty)

        summary = BestPracticeSummary(
            tenant_id=tenant_id,
            total_violations=len(all_violations),
            by_priority=by_priority,
            by_type=by_type,
            compliance_score=round(compliance_score, 2),
            evaluated_at=now,
        )

        return all_violations, summary

    # ------------------------------------------------------------------
    # Individual rule checks
    # ------------------------------------------------------------------

    def _check_stale_identity(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """StaleIdentity: last_seen > 90d = high, > 60d = medium, > 30d = low."""
        if identity.last_seen is None:
            return [
                self._build_violation(
                    tenant_id=tenant_id,
                    identity=identity,
                    violation_type=ViolationType.STALE_IDENTITY,
                    priority=ViolationPriority.HIGH,
                    title="Identity has never been observed",
                    description=(
                        f"Identity '{identity.display_name}' has no recorded activity. "
                        "Consider removing unused access."
                    ),
                    remediation_steps=[
                        "Review whether this identity still requires access.",
                        "Remove role assignments if the identity is no longer needed.",
                        "Consider disabling the account if it belongs to a departed user.",
                    ],
                    affected_roles=[r.role_name for r in identity.current_roles],
                ),
            ]

        now = datetime.now(UTC)
        last_seen = identity.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)

        days_inactive = (now - last_seen).days

        if days_inactive <= 30:
            return []

        if days_inactive > 90:
            priority = ViolationPriority.HIGH
        elif days_inactive > 60:
            priority = ViolationPriority.MEDIUM
        else:
            priority = ViolationPriority.LOW

        return [
            self._build_violation(
                tenant_id=tenant_id,
                identity=identity,
                violation_type=ViolationType.STALE_IDENTITY,
                priority=priority,
                title=f"Identity inactive for {days_inactive} days",
                description=(
                    f"Identity '{identity.display_name}' has not been active "
                    f"for {days_inactive} days. Stale access increases attack surface."
                ),
                remediation_steps=[
                    "Verify whether the identity still requires access.",
                    "Remove or reduce role assignments.",
                    "Enable access reviews for periodic recertification.",
                ],
                affected_roles=[r.role_name for r in identity.current_roles],
            ),
        ]

    def _check_permanent_admin(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """PermanentAdmin: permanent role with 'Administrator' or 'Global' in name."""
        violations: list[BestPracticeViolation] = []

        for role in identity.current_roles:
            if not role.is_permanent:
                continue
            name_lower = role.role_name.lower()
            if "administrator" not in name_lower and "global" not in name_lower:
                continue

            if "global administrator" in name_lower:
                priority = ViolationPriority.CRITICAL
            else:
                priority = ViolationPriority.HIGH

            violations.append(
                self._build_violation(
                    tenant_id=tenant_id,
                    identity=identity,
                    violation_type=ViolationType.PERMANENT_ADMIN,
                    priority=priority,
                    title=f"Permanent assignment to '{role.role_name}'",
                    description=(
                        f"Identity '{identity.display_name}' has a permanent "
                        f"assignment to '{role.role_name}'. Permanent admin roles "
                        "should be replaced with PIM eligible assignments."
                    ),
                    remediation_steps=[
                        f"Convert '{role.role_name}' to a PIM eligible assignment.",
                        "Set a maximum activation duration of 8 hours.",
                        "Require MFA and justification for activation.",
                    ],
                    affected_roles=[role.role_name],
                    # Use role-specific id suffix to allow multiple violations
                    id_suffix=f"{role.role_id}",
                ),
            )

        return violations

    def _check_no_pim(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """NoPIM: identity has admin roles but none via PIM."""
        admin_roles = [
            r for r in identity.current_roles
            if "administrator" in r.role_name.lower() or "global" in r.role_name.lower()
        ]

        if not admin_roles:
            return []

        has_pim = any(r.assignment_type == "pim" for r in admin_roles)
        if has_pim:
            return []

        return [
            self._build_violation(
                tenant_id=tenant_id,
                identity=identity,
                violation_type=ViolationType.NO_PIM,
                priority=ViolationPriority.MEDIUM,
                title="Admin roles not managed by PIM",
                description=(
                    f"Identity '{identity.display_name}' holds admin roles "
                    "but none are assigned via Privileged Identity Management (PIM). "
                    "PIM provides just-in-time access and audit trails."
                ),
                remediation_steps=[
                    "Enable PIM for the tenant if not already configured.",
                    "Convert direct admin role assignments to PIM eligible assignments.",
                    "Configure approval workflows for sensitive roles.",
                ],
                affected_roles=[r.role_name for r in admin_roles],
            ),
        ]

    async def _check_overprivileged(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """OverPrivileged: has recommendation with reduction_score > 30."""
        rec = await self._repo.get_recommendation(tenant_id, identity.id)
        if rec is None:
            return []

        if rec.reduction_score > 50:
            priority = ViolationPriority.HIGH
        elif rec.reduction_score > 30:
            priority = ViolationPriority.MEDIUM
        else:
            return []

        return [
            self._build_violation(
                tenant_id=tenant_id,
                identity=identity,
                violation_type=ViolationType.OVERPRIVILEGED,
                priority=priority,
                title=f"Overprivileged by {rec.reduction_score:.0f}%",
                description=(
                    f"Identity '{identity.display_name}' has {len(rec.permission_gaps)} "
                    f"unused permissions ({rec.reduction_score:.0f}% reduction possible). "
                    "Apply least-privilege by switching to a tighter role."
                ),
                remediation_steps=[
                    "Review the role recommendation for this identity.",
                    "Replace current roles with the recommended built-in or custom role.",
                    "Export the custom role definition via the IaC export endpoint.",
                ],
                affected_roles=[r.role_name for r in identity.current_roles],
            ),
        ]

    def _check_separation_of_duties(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """SeparationOfDuties: identity holds conflicting role pairs."""
        role_names = {r.role_name for r in identity.current_roles}
        violations: list[BestPracticeViolation] = []

        for role_a, role_b in _SOD_CONFLICTS:
            if role_a in role_names and role_b in role_names:
                violations.append(
                    self._build_violation(
                        tenant_id=tenant_id,
                        identity=identity,
                        violation_type=ViolationType.SEPARATION_OF_DUTIES,
                        priority=ViolationPriority.HIGH,
                        title=f"SoD conflict: '{role_a}' + '{role_b}'",
                        description=(
                            f"Identity '{identity.display_name}' holds both "
                            f"'{role_a}' and '{role_b}', which violates separation "
                            "of duties. This increases risk of privilege abuse."
                        ),
                        remediation_steps=[
                            f"Remove one of the conflicting roles ('{role_a}' or '{role_b}').",
                            "Assign conflicting duties to separate identities.",
                            "If both are required, document an exception with justification.",
                        ],
                        affected_roles=[role_a, role_b],
                        id_suffix=f"{role_a}_{role_b}",
                    ),
                )

        return violations

    def _check_role_assignable_group(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        """RoleAssignableGroup: Group identity with admin roles should use role-assignable groups."""
        if identity.identity_type != IdentityType.GROUP:
            return []

        admin_roles = [
            r for r in identity.current_roles
            if "administrator" in r.role_name.lower() or "global" in r.role_name.lower()
        ]

        if not admin_roles:
            return []

        return [
            self._build_violation(
                tenant_id=tenant_id,
                identity=identity,
                violation_type=ViolationType.ROLE_ASSIGNABLE_GROUP,
                priority=ViolationPriority.MEDIUM,
                title="Group with admin roles should be role-assignable",
                description=(
                    f"Group '{identity.display_name}' has admin role assignments. "
                    "Groups used for admin roles should be configured as "
                    "role-assignable groups to prevent membership changes by "
                    "non-privileged group owners."
                ),
                remediation_steps=[
                    "Recreate the group as a role-assignable group (cannot be changed after creation).",
                    "Restrict group ownership to privileged identities.",
                    "Enable access reviews for group membership.",
                ],
                affected_roles=[r.role_name for r in admin_roles],
            ),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_violation(
        *,
        tenant_id: str,
        identity: IdentityProfile,
        violation_type: ViolationType,
        priority: ViolationPriority,
        title: str,
        description: str,
        remediation_steps: list[str],
        affected_roles: list[str],
        id_suffix: str | None = None,
    ) -> BestPracticeViolation:
        """Construct a BestPracticeViolation with a deterministic id."""
        suffix = id_suffix or violation_type.value
        doc_id = f"{identity.id}_{suffix}"
        return BestPracticeViolation(
            id=doc_id,
            tenant_id=tenant_id,
            identity_id=identity.id,
            identity_display_name=identity.display_name,
            identity_type=identity.identity_type.value,
            violation_type=violation_type,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=remediation_steps,
            affected_roles=affected_roles,
            detected_at=datetime.now(UTC),
        )
