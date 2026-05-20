"""C1/C2: Analyzes OAuth consent grants and tenant consent policy settings."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.models.best_practice import (
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)

logger = logging.getLogger(__name__)

_HIGH_RISK_DELEGATED_SCOPES: set[str] = {
    "Mail.ReadWrite",
    "Mail.Send",
    "Files.ReadWrite.All",
    "Sites.ReadWrite.All",
    "User.ReadWrite.All",
    "Directory.ReadWrite.All",
    "RoleManagement.ReadWrite.Directory",
    "Application.ReadWrite.All",
    "MailboxSettings.ReadWrite",
    "Contacts.ReadWrite",
    "People.Read.All",
}

_MEDIUM_RISK_DELEGATED_SCOPES: set[str] = {
    "Mail.Read",
    "Files.Read.All",
    "Sites.Read.All",
    "Calendars.ReadWrite",
    "Notes.ReadWrite.All",
}


class ConsentAnalyzer:
    """Evaluates OAuth2 permission grants and tenant consent policies."""

    def evaluate_consent_grants(
        self,
        tenant_id: str,
        grants: list[dict[str, Any]],
        app_verification: dict[str, bool],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []

        for grant in grants:
            consent_type = grant.get("consentType", "")
            scope_str = grant.get("scope", "")
            scopes = set(scope_str.split()) if scope_str else set()
            client_id = grant.get("clientId", "")
            resource_id = grant.get("resourceId", "")
            principal_id = grant.get("principalId")

            is_user_consent = consent_type == "Principal" and principal_id
            is_verified = app_verification.get(client_id, True)

            high_risk_scopes = scopes & _HIGH_RISK_DELEGATED_SCOPES
            medium_risk_scopes = scopes & _MEDIUM_RISK_DELEGATED_SCOPES

            if high_risk_scopes:
                violations.append(
                    self._build(
                        tenant_id=tenant_id,
                        violation_type=ViolationType.RISKY_CONSENT_GRANT,
                        priority=ViolationPriority.CRITICAL,
                        title=f"High-risk consent grant: {', '.join(sorted(high_risk_scopes))}",
                        description=(
                            f"OAuth grant to app '{client_id}' includes high-risk "
                            f"delegated scopes: {', '.join(sorted(high_risk_scopes))}. "
                            "These permissions allow broad data access."
                        ),
                        id_suffix=f"consent_{client_id}_{resource_id}_highrisk",
                    )
                )

            if not is_verified and scopes:
                violations.append(
                    self._build(
                        tenant_id=tenant_id,
                        violation_type=ViolationType.UNVERIFIED_PUBLISHER_CONSENT,
                        priority=ViolationPriority.HIGH,
                        title=f"Consent grant to unverified publisher app '{client_id}'",
                        description=(
                            f"App '{client_id}' has consent grants but no verified "
                            "publisher. Unverified apps may be malicious consent "
                            "phishing attempts."
                        ),
                        id_suffix=f"consent_{client_id}_unverified",
                    )
                )

            if is_user_consent and (high_risk_scopes or medium_risk_scopes):
                risky = high_risk_scopes | medium_risk_scopes
                violations.append(
                    self._build(
                        tenant_id=tenant_id,
                        violation_type=ViolationType.USER_CONSENT_HIGH_PRIVILEGE,
                        priority=ViolationPriority.HIGH,
                        title=f"User-consented high-privilege scopes: {', '.join(sorted(risky))}",
                        description=(
                            f"User '{principal_id}' directly consented to app "
                            f"'{client_id}' for scopes: {', '.join(sorted(risky))}. "
                            "High-privilege scopes should require admin consent."
                        ),
                        id_suffix=f"consent_{client_id}_{principal_id}_userconsent",
                    )
                )

        return violations

    def evaluate_consent_policy(
        self,
        tenant_id: str,
        auth_policy: dict[str, Any],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []

        default_user_role = auth_policy.get("defaultUserRolePermissions", {})
        can_consent = default_user_role.get(
            "permissionGrantPoliciesAssigned", []
        )

        allows_user_consent = any(
            "ManagePermissionGrantsForSelf" in p or "microsoft-user-default-legacy" in p
            for p in can_consent
        )
        if allows_user_consent:
            violations.append(
                self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.USER_CONSENT_UNRESTRICTED,
                    priority=ViolationPriority.HIGH,
                    title="Users can consent to apps without admin approval",
                    description=(
                        "The tenant's authorization policy allows users to consent "
                        "to third-party apps. This enables consent phishing attacks. "
                        "Restrict user consent to verified publishers or admin-approved apps."
                    ),
                    id_suffix="consent_policy_unrestricted",
                )
            )

        admin_consent_enabled = auth_policy.get(
            "isAdminConsentRequestEnabled", False
        )
        if not admin_consent_enabled:
            violations.append(
                self._build(
                    tenant_id=tenant_id,
                    violation_type=ViolationType.NO_ADMIN_CONSENT_WORKFLOW,
                    priority=ViolationPriority.MEDIUM,
                    title="Admin consent workflow not enabled",
                    description=(
                        "The admin consent request workflow is not enabled. "
                        "Without it, users who need app access have no path to "
                        "request admin approval, leading to shadow IT."
                    ),
                    id_suffix="consent_policy_no_workflow",
                )
            )

        return violations

    @staticmethod
    def _build(
        *,
        tenant_id: str,
        violation_type: ViolationType,
        priority: ViolationPriority,
        title: str,
        description: str,
        id_suffix: str,
    ) -> BestPracticeViolation:
        return BestPracticeViolation(
            id=f"consent_{tenant_id}_{id_suffix}",
            tenant_id=tenant_id,
            identity_id=f"tenant_{tenant_id}",
            identity_display_name="Tenant Policy",
            identity_type="Tenant",
            violation_type=violation_type,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=[
                "Review and revoke suspicious consent grants in the Entra admin center.",
                "Restrict user consent to verified publisher apps only.",
                "Enable the admin consent workflow for legitimate app requests.",
            ],
            affected_roles=[],
            detected_at=datetime.now(UTC),
        )
