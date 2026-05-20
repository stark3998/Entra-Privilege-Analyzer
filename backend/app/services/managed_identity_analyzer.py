"""B3: Analyzes managed identity configurations for security best practices."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.models.best_practice import (
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)
from app.models.identity import IdentityProfile, IdentityType

logger = logging.getLogger(__name__)

_ADMIN_ROLE_PATTERNS = (
    "global administrator",
    "privileged role administrator",
    "privileged authentication administrator",
    "security administrator",
    "application administrator",
    "user administrator",
)

_BROAD_SCOPE_PATTERN = "/"


class ManagedIdentityAnalyzer:
    """Evaluates managed identities for overprivilege and scope issues."""

    def evaluate(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        if identity.identity_type != IdentityType.MANAGED_IDENTITY:
            return []

        violations: list[BestPracticeViolation] = []
        violations.extend(self._check_overprivileged_mi(tenant_id, identity))
        violations.extend(self._check_broad_scope(tenant_id, identity))
        return violations

    def _check_overprivileged_mi(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        admin_roles = [
            r for r in identity.current_roles
            if r.role_name.lower() in _ADMIN_ROLE_PATTERNS
        ]
        if not admin_roles:
            return []

        is_ga = any("global administrator" in r.role_name.lower() for r in admin_roles)

        return [
            self._build(
                tenant_id=tenant_id,
                identity=identity,
                violation_type=ViolationType.MI_OVERPRIVILEGED,
                priority=ViolationPriority.CRITICAL if is_ga else ViolationPriority.HIGH,
                title=f"Managed identity has admin role(s): {', '.join(r.role_name for r in admin_roles[:3])}",
                description=(
                    f"Managed identity '{identity.display_name}' holds "
                    f"{len(admin_roles)} admin role(s). Managed identities "
                    "should follow least privilege — admin roles are almost "
                    "never necessary for automated workloads."
                ),
                id_suffix="mi_admin",
            ),
        ]

    def _check_broad_scope(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[BestPracticeViolation]:
        broad_roles = [
            r for r in identity.current_roles
            if r.scope == _BROAD_SCOPE_PATTERN or r.scope == ""
        ]
        if not broad_roles:
            return []

        scoped_roles = [
            r for r in identity.current_roles
            if r.scope and r.scope != _BROAD_SCOPE_PATTERN and r.scope != ""
        ]
        if scoped_roles:
            return []

        return [
            self._build(
                tenant_id=tenant_id,
                identity=identity,
                violation_type=ViolationType.MI_BROAD_SCOPE,
                priority=ViolationPriority.MEDIUM,
                title=f"Managed identity has {len(broad_roles)} role(s) at root scope",
                description=(
                    f"Managed identity '{identity.display_name}' has all "
                    f"{len(broad_roles)} role assignments at the root scope. "
                    "Scope roles to the specific resource group or subscription "
                    "where the workload runs."
                ),
                id_suffix="mi_broad_scope",
            ),
        ]

    @staticmethod
    def _build(
        *,
        tenant_id: str,
        identity: IdentityProfile,
        violation_type: ViolationType,
        priority: ViolationPriority,
        title: str,
        description: str,
        id_suffix: str,
    ) -> BestPracticeViolation:
        return BestPracticeViolation(
            id=f"{identity.id}_{id_suffix}",
            tenant_id=tenant_id,
            identity_id=identity.id,
            identity_display_name=identity.display_name,
            identity_type=identity.identity_type.value,
            violation_type=violation_type,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=[
                "Replace admin roles with least-privilege built-in or custom roles.",
                "Scope role assignments to the specific resource group or subscription.",
                "Review whether the managed identity is still needed.",
            ],
            affected_roles=[r.role_name for r in identity.current_roles],
            detected_at=datetime.now(UTC),
        )
