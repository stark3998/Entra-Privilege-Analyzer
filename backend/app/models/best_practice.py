# backend/app/models/best_practice.py
"""Pydantic v2 models for best practice violation analysis."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ViolationType(StrEnum):
    """Categories of best practice violations."""

    STALE_IDENTITY = "stale_identity"
    PERMANENT_ADMIN = "permanent_admin"
    NO_PIM = "no_pim"
    SP_CREDENTIAL_EXPIRY = "sp_credential_expiry"
    SEPARATION_OF_DUTIES = "separation_of_duties"
    OVERPRIVILEGED = "overprivileged"
    MFA_GAP = "mfa_gap"
    ROLE_ASSIGNABLE_GROUP = "role_assignable_group"

    # App registration (Phase 1.2)
    APP_NO_OWNER = "app_no_owner"
    APP_MULTI_TENANT = "app_multi_tenant"
    APP_EXCESSIVE_PERMISSIONS = "app_excessive_permissions"
    APP_STALE_CREDENTIAL = "app_stale_credential"

    # Guest governance (Phase 2.4)
    GUEST_STALE = "guest_stale"
    GUEST_PENDING_INVITATION = "guest_pending_invitation"
    GUEST_ADMIN = "guest_admin"
    GUEST_NO_MFA = "guest_no_mfa"

    # Identity lifecycle (Phase D)
    ORPHANED_ACCOUNT = "orphaned_account"
    INCOMPLETE_OFFBOARDING = "incomplete_offboarding"
    NEVER_USED_ACCOUNT = "never_used_account"

    # SP workload identity (Phase B)
    SP_OVERPRIVILEGED = "sp_overprivileged"
    SP_UNUSED_PERMISSIONS = "sp_unused_permissions"
    SP_UNUSED_CREDENTIAL = "sp_unused_credential"
    SP_MULTIPLE_ACTIVE_CREDENTIALS = "sp_multiple_active_credentials"
    MI_OVERPRIVILEGED = "mi_overprivileged"
    MI_BROAD_SCOPE = "mi_broad_scope"
    FEDERATION_BROAD_SUBJECT = "federation_broad_subject"
    FEDERATION_NO_AUDIENCE = "federation_no_audience"

    # OAuth consent (Phase C)
    RISKY_CONSENT_GRANT = "risky_consent_grant"
    UNVERIFIED_PUBLISHER_CONSENT = "unverified_publisher_consent"
    USER_CONSENT_HIGH_PRIVILEGE = "user_consent_high_privilege"
    USER_CONSENT_UNRESTRICTED = "user_consent_unrestricted"
    NO_ADMIN_CONSENT_WORKFLOW = "no_admin_consent_workflow"

    # Conditional Access (Phase 2.1)
    CA_LEGACY_AUTH_NOT_BLOCKED = "ca_legacy_auth_not_blocked"
    CA_NO_MFA_FOR_ADMINS = "ca_no_mfa_for_admins"
    CA_NO_MFA_FOR_ALL = "ca_no_mfa_for_all"
    CA_EXCESSIVE_EXCLUSIONS = "ca_excessive_exclusions"
    CA_ADMIN_EXCLUDED = "ca_admin_excluded"
    CA_NO_RISK_POLICY = "ca_no_risk_policy"
    CA_REPORT_ONLY_CRITICAL = "ca_report_only_critical"
    CA_NO_DEVICE_COMPLIANCE = "ca_no_device_compliance"
    CA_NO_GUEST_MFA = "ca_no_guest_mfa"
    CA_GRANT_OR_OPERATOR = "ca_grant_or_operator"
    CA_NO_AZURE_MGMT_MFA = "ca_no_azure_mgmt_mfa"
    CA_ALL_APPS_EXCLUSIONS = "ca_all_apps_exclusions"


class ViolationPriority(StrEnum):
    """Priority level for a violation."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BestPracticeViolation(BaseModel):
    """A single best practice violation for an identity."""

    model_config = ConfigDict(extra="ignore")

    id: str  # {identity_id}_{violation_type}
    tenant_id: str
    identity_id: str
    identity_display_name: str
    identity_type: str
    violation_type: ViolationType
    priority: ViolationPriority
    title: str
    description: str
    remediation_steps: list[str]
    affected_roles: list[str]
    detected_at: datetime
    resolved: bool = False


class BestPracticeSummary(BaseModel):
    """Aggregated compliance summary for a tenant."""

    tenant_id: str
    total_violations: int
    by_priority: dict[str, int]
    by_type: dict[str, int]
    compliance_score: float  # 0-100
    evaluated_at: datetime
