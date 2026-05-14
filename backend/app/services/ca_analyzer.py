# backend/app/services/ca_analyzer.py
"""Conditional Access policy analyzer — 12 tenant-level checks."""
from __future__ import annotations

from datetime import UTC, datetime

from app.models.best_practice import (
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)
from app.models.conditional_access import ConditionalAccessPolicyRecord

# Well-known Entra ID admin role template IDs
_ADMIN_ROLE_IDS: set[str] = {
    "62e90394-69f5-4237-9190-012177145e10",  # Global Administrator
    "e8611ab8-c189-46e8-94e1-60213ab1f814",  # Privileged Role Administrator
    "194ae4cb-b126-40b2-bd5b-6091b380977d",  # Security Administrator
    "b1be1c3e-b65d-4f19-8427-f6fa0d97feb9",  # Conditional Access Administrator
}

# Azure Management app ID
_AZURE_MGMT_APP_ID = "797f4846-ba00-4fd7-ba43-dac1f8f63013"

# Legacy auth client app types
_LEGACY_AUTH_TYPES: set[str] = {"exchangeActiveSync", "other"}


class ConditionalAccessAnalyzer:
    """Evaluates Conditional Access policies against 12 security checks."""

    def evaluate_policies(
        self,
        tenant_id: str,
        policies: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        """Run all CA checks and return violations."""
        violations: list[BestPracticeViolation] = []
        enabled = [p for p in policies if p.state == "enabled"]

        violations.extend(self._check_legacy_auth_blocked(tenant_id, enabled))
        violations.extend(self._check_mfa_for_admins(tenant_id, enabled))
        violations.extend(self._check_mfa_for_all_users(tenant_id, enabled))
        violations.extend(self._check_excessive_exclusions(tenant_id, enabled))
        violations.extend(self._check_admin_excluded(tenant_id, enabled))
        violations.extend(self._check_risk_based_policy(tenant_id, enabled))
        violations.extend(self._check_report_only_critical(tenant_id, policies))
        violations.extend(self._check_device_compliance(tenant_id, enabled))
        violations.extend(self._check_guest_mfa(tenant_id, enabled))
        violations.extend(self._check_grant_or_operator(tenant_id, enabled))
        violations.extend(self._check_azure_management_mfa(tenant_id, enabled))
        violations.extend(self._check_all_apps_exclusions(tenant_id, enabled))

        return violations

    # ------------------------------------------------------------------
    # Check 1: Legacy authentication not blocked
    # ------------------------------------------------------------------

    def _check_legacy_auth_blocked(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        for p in enabled:
            client_types = set(p.conditions.client_app_types)
            if _LEGACY_AUTH_TYPES.issubset(client_types) and p.grant_controls is None:
                # Block grant (no grant_controls means block) — policy exists
                return []
            if (
                _LEGACY_AUTH_TYPES.issubset(client_types)
                and p.grant_controls is not None
                and "block" in p.grant_controls.built_in_controls
            ):
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_LEGACY_AUTH_NOT_BLOCKED,
            priority=ViolationPriority.CRITICAL,
            title="Legacy authentication not blocked",
            description="No enabled CA policy blocks legacy authentication (exchangeActiveSync + other). Legacy auth bypasses MFA.",
            remediation_steps=[
                "Create a CA policy targeting all users with client app types 'Exchange ActiveSync' and 'Other clients'.",
                "Set grant controls to 'Block access'.",
                "Monitor in report-only mode first, then enable.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 2: No MFA for admins
    # ------------------------------------------------------------------

    def _check_mfa_for_admins(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        for p in enabled:
            targeted_roles = set(p.conditions.users.include_roles)
            if not targeted_roles.intersection(_ADMIN_ROLE_IDS):
                continue
            if p.grant_controls and "mfa" in p.grant_controls.built_in_controls:
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_NO_MFA_FOR_ADMINS,
            priority=ViolationPriority.CRITICAL,
            title="No MFA required for admin roles",
            description="No enabled CA policy requires MFA for Global Admin, Privileged Role Admin, Security Admin, or CA Admin.",
            remediation_steps=[
                "Create a CA policy targeting admin directory roles.",
                "Require MFA or phishing-resistant authentication strength.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 3: No MFA for all users
    # ------------------------------------------------------------------

    def _check_mfa_for_all_users(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        for p in enabled:
            if (
                "All" in p.conditions.users.include_users
                and "All" in p.conditions.include_applications
                and p.grant_controls
                and "mfa" in p.grant_controls.built_in_controls
            ):
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_NO_MFA_FOR_ALL,
            priority=ViolationPriority.HIGH,
            title="No MFA required for all users and all apps",
            description="No enabled CA policy requires MFA for all users across all applications.",
            remediation_steps=[
                "Create a CA policy targeting all users and all cloud apps with MFA requirement.",
                "Exclude emergency access (break-glass) accounts only.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 4: Excessive exclusions on MFA policies
    # ------------------------------------------------------------------

    def _check_excessive_exclusions(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []
        for p in enabled:
            if not (p.grant_controls and "mfa" in p.grant_controls.built_in_controls):
                continue
            exclusion_count = (
                len(p.conditions.users.exclude_users)
                + len(p.conditions.users.exclude_groups)
            )
            if exclusion_count > 5:
                violations.append(self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.CA_EXCESSIVE_EXCLUSIONS,
                    priority=ViolationPriority.HIGH,
                    title=f"MFA policy '{p.display_name}' has {exclusion_count} exclusions",
                    description=f"Policy '{p.display_name}' excludes {exclusion_count} users/groups from MFA. Excessive exclusions weaken security posture.",
                    remediation_steps=[
                        "Review and reduce user/group exclusions to break-glass accounts only.",
                        "Use named locations or compliant device grants instead of user exclusions.",
                    ],
                    policy_id=p.id,
                ))
        return violations

    # ------------------------------------------------------------------
    # Check 5: Admin roles excluded from MFA
    # ------------------------------------------------------------------

    def _check_admin_excluded(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []
        for p in enabled:
            if not (p.grant_controls and "mfa" in p.grant_controls.built_in_controls):
                continue
            excluded_admin_roles = set(p.conditions.users.exclude_roles).intersection(_ADMIN_ROLE_IDS)
            if excluded_admin_roles:
                violations.append(self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.CA_ADMIN_EXCLUDED,
                    priority=ViolationPriority.CRITICAL,
                    title=f"Admin roles excluded from MFA in '{p.display_name}'",
                    description=f"Policy '{p.display_name}' excludes {len(excluded_admin_roles)} admin role(s) from MFA. Admins must never be excluded.",
                    remediation_steps=[
                        "Remove admin role exclusions from this policy immediately.",
                        "Create a separate CA policy specifically for admin roles if different controls are needed.",
                    ],
                    policy_id=p.id,
                ))
        return violations

    # ------------------------------------------------------------------
    # Check 6: No risk-based policy
    # ------------------------------------------------------------------

    def _check_risk_based_policy(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        for p in enabled:
            if p.conditions.sign_in_risk_levels or p.conditions.user_risk_levels:
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_NO_RISK_POLICY,
            priority=ViolationPriority.HIGH,
            title="No risk-based Conditional Access policy",
            description="No enabled CA policy uses sign-in risk or user risk levels. Risk-based policies are essential for Identity Protection.",
            remediation_steps=[
                "Create a policy requiring MFA for medium+ sign-in risk.",
                "Create a policy requiring password change for high user risk.",
                "Ensure Entra ID P2 licensing is in place for risk detection.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 7: Critical policies in report-only mode
    # ------------------------------------------------------------------

    def _check_report_only_critical(
        self,
        tenant_id: str,
        all_policies: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []
        report_only = [
            p for p in all_policies
            if p.state == "enabledForReportingButNotEnforced"
        ]
        for p in report_only:
            client_types = set(p.conditions.client_app_types)
            is_legacy_block = _LEGACY_AUTH_TYPES.issubset(client_types)
            is_all_users_mfa = (
                "All" in p.conditions.users.include_users
                and "All" in p.conditions.include_applications
                and p.grant_controls is not None
                and "mfa" in p.grant_controls.built_in_controls
            )
            if is_legacy_block or is_all_users_mfa:
                violations.append(self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.CA_REPORT_ONLY_CRITICAL,
                    priority=ViolationPriority.MEDIUM,
                    title=f"Critical policy '{p.display_name}' is report-only",
                    description=f"Policy '{p.display_name}' is in report-only mode but covers a critical control (legacy auth block or all-users MFA). Enable it after review.",
                    remediation_steps=[
                        "Review the policy's report-only impact in the sign-in logs.",
                        "Switch the policy state to 'enabled' once impact is acceptable.",
                    ],
                    policy_id=p.id,
                ))
        return violations

    # ------------------------------------------------------------------
    # Check 8: No device compliance policy
    # ------------------------------------------------------------------

    def _check_device_compliance(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        compliance_controls = {"compliantDevice", "domainJoinedDevice"}
        for p in enabled:
            if p.grant_controls and compliance_controls.intersection(p.grant_controls.built_in_controls):
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_NO_DEVICE_COMPLIANCE,
            priority=ViolationPriority.MEDIUM,
            title="No device compliance requirement in CA policies",
            description="No enabled CA policy requires a compliant or domain-joined device. Device compliance adds a strong signal for access decisions.",
            remediation_steps=[
                "Create a CA policy requiring compliant device for corporate app access.",
                "Ensure Intune device compliance policies are configured.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 9: No MFA for guest users
    # ------------------------------------------------------------------

    def _check_guest_mfa(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        for p in enabled:
            targets_guests = "GuestsOrExternalUsers" in p.conditions.users.include_users
            has_mfa = p.grant_controls and "mfa" in p.grant_controls.built_in_controls
            if targets_guests and has_mfa:
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_NO_GUEST_MFA,
            priority=ViolationPriority.HIGH,
            title="No MFA required for guest/external users",
            description="No enabled CA policy requires MFA specifically for guest or external users.",
            remediation_steps=[
                "Create a CA policy targeting 'Guest or external users' with MFA requirement.",
                "Consider requiring phishing-resistant MFA for guests accessing sensitive apps.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 10: Grant controls with OR operator and multiple controls
    # ------------------------------------------------------------------

    def _check_grant_or_operator(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []
        for p in enabled:
            if (
                p.grant_controls
                and p.grant_controls.operator == "OR"
                and len(p.grant_controls.built_in_controls) > 1
            ):
                controls = ", ".join(p.grant_controls.built_in_controls)
                violations.append(self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.CA_GRANT_OR_OPERATOR,
                    priority=ViolationPriority.MEDIUM,
                    title=f"OR operator with multiple grant controls in '{p.display_name}'",
                    description=f"Policy '{p.display_name}' uses OR between [{controls}]. Users can satisfy the weakest control. Use AND for defense in depth.",
                    remediation_steps=[
                        "Change the grant operator to 'AND' to require all controls.",
                        "If OR is intentional, document the justification.",
                    ],
                    policy_id=p.id,
                ))
        return violations

    # ------------------------------------------------------------------
    # Check 11: No MFA for Azure Management
    # ------------------------------------------------------------------

    def _check_azure_management_mfa(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        for p in enabled:
            targets_azure_mgmt = _AZURE_MGMT_APP_ID in p.conditions.include_applications
            has_mfa = p.grant_controls and "mfa" in p.grant_controls.built_in_controls
            if targets_azure_mgmt and has_mfa:
                return []
        return [self._build(
            tenant_id=tenant_id,
            violation_type=ViolationType.CA_NO_AZURE_MGMT_MFA,
            priority=ViolationPriority.HIGH,
            title="No MFA required for Azure Management",
            description=f"No enabled CA policy requires MFA for the Azure Management app ({_AZURE_MGMT_APP_ID}). Portal and CLI access should require MFA.",
            remediation_steps=[
                "Create a CA policy targeting the 'Microsoft Azure Management' cloud app.",
                "Require MFA or phishing-resistant authentication strength.",
            ],
        )]

    # ------------------------------------------------------------------
    # Check 12: All-apps policy with application exclusions
    # ------------------------------------------------------------------

    def _check_all_apps_exclusions(
        self,
        tenant_id: str,
        enabled: list[ConditionalAccessPolicyRecord],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []
        for p in enabled:
            if (
                "All" in p.conditions.include_applications
                and p.conditions.exclude_applications
            ):
                count = len(p.conditions.exclude_applications)
                violations.append(self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.CA_ALL_APPS_EXCLUSIONS,
                    priority=ViolationPriority.MEDIUM,
                    title=f"All-apps policy '{p.display_name}' excludes {count} app(s)",
                    description=f"Policy '{p.display_name}' targets all applications but excludes {count}. Excluded apps bypass this policy's controls.",
                    remediation_steps=[
                        "Review excluded applications and remove unnecessary exclusions.",
                        "Create separate policies for apps that need different controls.",
                    ],
                    policy_id=p.id,
                ))
        return violations

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build(
        *,
        tenant_id: str,
        violation_type: ViolationType,
        priority: ViolationPriority,
        title: str,
        description: str,
        remediation_steps: list[str] | None = None,
        policy_id: str | None = None,
    ) -> BestPracticeViolation:
        """Build a tenant-level CA violation with a deterministic ID."""
        if policy_id:
            doc_id = f"ca_{tenant_id}_{violation_type.value}_{policy_id}"
        else:
            doc_id = f"ca_{tenant_id}_{violation_type.value}"
        return BestPracticeViolation(
            id=doc_id,
            tenant_id=tenant_id,
            identity_id=f"tenant_{tenant_id}",
            identity_display_name="Tenant Policy",
            identity_type="Tenant",
            violation_type=violation_type,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=remediation_steps or [],
            affected_roles=[],
            detected_at=datetime.now(UTC),
        )
