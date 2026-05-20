"""B1: Analyzes service principal permission usage — granted vs. actually used."""

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

_HIGH_RISK_APP_PERMISSIONS: set[str] = {
    "Directory.ReadWrite.All",
    "RoleManagement.ReadWrite.Directory",
    "Application.ReadWrite.All",
    "AppRoleAssignment.ReadWrite.All",
    "Mail.ReadWrite",
    "Files.ReadWrite.All",
    "Sites.ReadWrite.All",
    "User.ReadWrite.All",
    "Group.ReadWrite.All",
}


class SpPermissionAnalyzer:
    """Compares SP granted permissions against observed usage to find unused privileges."""

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    async def analyze_sp(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        granted_permissions: list[str],
    ) -> list[BestPracticeViolation]:
        if identity.identity_type != IdentityType.SERVICE_PRINCIPAL:
            return []
        if not granted_permissions:
            return []

        observed_resources = {
            oa.resource for oa in identity.observed_actions if oa.resource
        }
        observed_actions = {oa.action for oa in identity.observed_actions}

        used_permissions: set[str] = set()
        for perm in granted_permissions:
            perm_resource = perm.split(".")[0] if "." in perm else perm
            if any(perm_resource.lower() in r.lower() for r in observed_resources):
                used_permissions.add(perm)
            if any(perm_resource.lower() in a.lower() for a in observed_actions):
                used_permissions.add(perm)

        unused_permissions = set(granted_permissions) - used_permissions

        if not unused_permissions:
            return []

        violations: list[BestPracticeViolation] = []

        high_risk_unused = unused_permissions & _HIGH_RISK_APP_PERMISSIONS
        if high_risk_unused:
            violations.append(
                self._build_violation(
                    tenant_id=tenant_id,
                    identity=identity,
                    violation_type=ViolationType.SP_OVERPRIVILEGED,
                    priority=ViolationPriority.CRITICAL,
                    title=f"SP has {len(high_risk_unused)} unused high-risk permission(s)",
                    description=(
                        f"Service principal '{identity.display_name}' has been granted "
                        f"high-risk permissions that are never used: "
                        f"{', '.join(sorted(high_risk_unused))}. "
                        "Remove these to reduce blast radius."
                    ),
                    id_suffix="sp_unused_highrisk",
                )
            )

        other_unused = unused_permissions - _HIGH_RISK_APP_PERMISSIONS
        if other_unused and len(other_unused) >= 3:
            violations.append(
                self._build_violation(
                    tenant_id=tenant_id,
                    identity=identity,
                    violation_type=ViolationType.SP_UNUSED_PERMISSIONS,
                    priority=ViolationPriority.HIGH,
                    title=f"SP has {len(other_unused)} unused permission(s)",
                    description=(
                        f"Service principal '{identity.display_name}' has "
                        f"{len(other_unused)} granted permissions with no observed "
                        f"usage: {', '.join(sorted(list(other_unused)[:5]))}."
                    ),
                    id_suffix="sp_unused_perms",
                )
            )

        return violations

    @staticmethod
    def _build_violation(
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
                "Review the unused permissions and remove those not required.",
                "Use Microsoft Graph activity logs to confirm which permissions are used.",
                "Consider migrating to managed identity for Azure-hosted workloads.",
            ],
            affected_roles=[r.role_name for r in identity.current_roles],
            detected_at=datetime.now(UTC),
        )
