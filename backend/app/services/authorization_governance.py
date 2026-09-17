from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.models.governance import ApprovalPolicy, GovernanceRole, RiskAssessment


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    autonomous: bool
    requires_human_approval: bool
    reasons: tuple[str, ...]


class AuthorizationGovernanceService:
    """Evaluates capability roles and non-bypassable remediation safety policy."""

    _CAPABILITIES: ClassVar[dict[GovernanceRole, frozenset[str]]] = {
        GovernanceRole.POLICY_ADMIN: frozenset({"policy.read", "policy.write"}),
        GovernanceRole.REMEDIATION_APPROVER: frozenset(
            {"workflow.read", "workflow.approve"}
        ),
        GovernanceRole.ACCESS_OWNER: frozenset(
            {"workflow.read", "workflow.request", "evidence.read"}
        ),
        GovernanceRole.AUDITOR: frozenset(
            {"workflow.read", "evidence.read", "audit.read"}
        ),
        GovernanceRole.EMERGENCY_OPERATOR: frozenset(
            {"workflow.read", "restore.execute", "incident.execute"}
        ),
    }
    _LEGACY_CAPABILITIES: ClassVar[dict[str, frozenset[str]]] = {
        "IAMAdmin": frozenset(
            {
                "policy.read",
                "policy.write",
                "workflow.read",
                "workflow.request",
                "workflow.approve",
                "evidence.read",
                "audit.read",
                "restore.execute",
                "incident.execute",
            }
        ),
        "SecurityEngineer": frozenset(
            {
                "policy.read",
                "workflow.read",
                "workflow.request",
                "evidence.read",
                "audit.read",
            }
        ),
        "Executive": frozenset({"workflow.read", "evidence.read", "audit.read"}),
    }

    def require_capability(self, roles: list[str], capability: str) -> None:
        granted = {
            permission
            for role_name in roles
            if role_name in GovernanceRole._value2member_map_
            for permission in self._CAPABILITIES[GovernanceRole(role_name)]
        }
        granted.update(
            permission
            for role_name in roles
            for permission in self._LEGACY_CAPABILITIES.get(role_name, frozenset())
        )
        if capability not in granted:
            raise PermissionError(f"Missing governance capability: {capability}")

    def evaluate_remediation(
        self,
        policy: ApprovalPolicy,
        assessment: RiskAssessment,
        *,
        identity_id: str,
        role_tier: str,
        is_last_global_admin: bool = False,
    ) -> PolicyDecision:
        reasons: list[str] = []
        if identity_id in policy.break_glass_identity_ids:
            return PolicyDecision(False, False, True, ("break_glass_identity",))
        if policy.last_global_admin_protection and is_last_global_admin:
            return PolicyDecision(False, False, True, ("last_global_admin",))
        autonomous = True
        if role_tier not in policy.autonomous_role_tiers:
            autonomous = False
            reasons.append("role_tier_requires_approval")
        if assessment.impact > policy.autonomous_max_impact:
            autonomous = False
            reasons.append("impact_requires_approval")
        if assessment.confidence < policy.autonomous_min_confidence:
            autonomous = False
            reasons.append("insufficient_confidence")
        if assessment.impact >= policy.high_impact_threshold:
            autonomous = False
            reasons.append("high_impact_human_approval_required")
        return PolicyDecision(True, autonomous, not autonomous, tuple(reasons))
