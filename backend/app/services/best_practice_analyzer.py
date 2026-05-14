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
from app.models.app_registration import AppRegistrationProfile, HIGH_RISK_APP_PERMISSION_GUIDS
from app.models.identity import IdentityProfile, IdentityType
from app.models.mfa_status import MfaRegistrationRecord, PHISHING_RESISTANT_METHODS, WEAK_MFA_METHODS
from app.models.sod_policy import SodConflictRule, DEFAULT_SOD_RULES, build_default_rules
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
        sod_rules: list[tuple[str, str, str]] | None = None,
    ) -> list[BestPracticeViolation]:
        """Run all best practice rules against a single identity."""
        violations: list[BestPracticeViolation] = []

        violations.extend(self._check_stale_identity(tenant_id, identity))
        violations.extend(self._check_permanent_admin(tenant_id, identity))
        violations.extend(self._check_no_pim(tenant_id, identity))
        violations.extend(await self._check_overprivileged(tenant_id, identity))
        violations.extend(self._check_separation_of_duties(tenant_id, identity, sod_rules))
        violations.extend(self._check_role_assignable_group(tenant_id, identity))

        return violations

    async def evaluate_tenant(
        self,
        tenant_id: str,
    ) -> tuple[list[BestPracticeViolation], BestPracticeSummary]:
        """Evaluate all identities in a tenant and compute compliance summary."""
        now = datetime.now(UTC)
        all_violations: list[BestPracticeViolation] = []

        # Load dynamic SoD rules (fall back to defaults if none stored)
        sod_rules_raw = await self._repo.get_sod_rules(tenant_id)
        if sod_rules_raw:
            sod_pairs = [
                (r.role_a_name, r.role_b_name, r.severity)
                for r in sod_rules_raw if r.enabled
            ]
        else:
            sod_pairs = [
                (r["role_a"], r["role_b"], r["severity"])
                for r in DEFAULT_SOD_RULES
            ]

        # Paginate through all identities
        offset = 0
        page_size = 100
        while True:
            items, total = await self._repo.list_identities(
                tenant_id=tenant_id, offset=offset, limit=page_size,
            )
            for identity in items:
                try:
                    violations = await self.evaluate_identity(
                        tenant_id, identity, sod_rules=sod_pairs,
                    )
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

        # Run tenant-level analyzers (CA policies, groups, custom roles, access reviews)
        try:
            from app.services.ca_analyzer import ConditionalAccessAnalyzer
            ca_policies = await self._repo.list_ca_policies(tenant_id)
            if ca_policies:
                ca_analyzer = ConditionalAccessAnalyzer()
                all_violations.extend(ca_analyzer.evaluate_policies(tenant_id, ca_policies))
        except Exception:
            logger.exception("CA policy analysis failed for %s", tenant_id)

        try:
            from app.services.group_analyzer import GroupAnalyzer
            groups_list, _ = await self._repo.list_groups(tenant_id, offset=0, limit=5000)
            if groups_list:
                ga = GroupAnalyzer()
                all_violations.extend(ga.evaluate_groups(tenant_id, groups_list))
        except Exception:
            logger.exception("Group analysis failed for %s", tenant_id)

        try:
            from app.services.custom_role_analyzer import CustomRoleAnalyzer
            custom_roles = await self._repo.list_custom_roles(tenant_id)
            if custom_roles:
                cra = CustomRoleAnalyzer()
                all_violations.extend(cra.evaluate_custom_roles(tenant_id, custom_roles))
        except Exception:
            logger.exception("Custom role analysis failed for %s", tenant_id)

        try:
            from app.services.access_review_analyzer import AccessReviewAnalyzer
            reviews = await self._repo.list_access_reviews(tenant_id)
            if reviews:
                identities_all, _ = await self._repo.list_identities(tenant_id, offset=0, limit=5000)
                groups_for_review, _ = await self._repo.list_groups(tenant_id, offset=0, limit=5000)
                privileged_role_ids = set()
                role_assignable_group_ids = set()
                for identity in identities_all:
                    for role in identity.current_roles:
                        if "administrator" in role.role_name.lower() or "global" in role.role_name.lower():
                            privileged_role_ids.add(role.role_id)
                for g in groups_for_review:
                    if g.is_role_assignable:
                        role_assignable_group_ids.add(g.id)
                has_guests = any(
                    getattr(i, "user_type", None) == "Guest" for i in identities_all
                )
                ara = AccessReviewAnalyzer()
                all_violations.extend(
                    ara.evaluate_coverage(tenant_id, reviews, privileged_role_ids, role_assignable_group_ids, has_guests)
                )
        except Exception:
            logger.exception("Access review analysis failed for %s", tenant_id)

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

        pim_types = {"pim", "pim_eligible", "pim_activated"}
        has_pim = any(r.assignment_type in pim_types for r in admin_roles)
        has_eligible = bool(identity.eligible_roles)
        if has_pim or has_eligible:
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
        sod_rules: list[tuple[str, str, str]] | None = None,
    ) -> list[BestPracticeViolation]:
        """SeparationOfDuties: identity holds conflicting role pairs."""
        role_names = {r.role_name for r in identity.current_roles}
        violations: list[BestPracticeViolation] = []

        rules = sod_rules or [(a, b, "high") for a, b in _SOD_CONFLICTS]

        _severity_map = {
            "critical": ViolationPriority.CRITICAL,
            "high": ViolationPriority.HIGH,
            "medium": ViolationPriority.MEDIUM,
            "low": ViolationPriority.LOW,
        }

        for role_a, role_b, severity in rules:
            if role_a in role_names and role_b in role_names:
                violations.append(
                    self._build_violation(
                        tenant_id=tenant_id,
                        identity=identity,
                        violation_type=ViolationType.SEPARATION_OF_DUTIES,
                        priority=_severity_map.get(severity, ViolationPriority.HIGH),
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
    # App registration checks (Phase 1.2)
    # ------------------------------------------------------------------

    def evaluate_app_registration(
        self,
        tenant_id: str,
        app: AppRegistrationProfile,
    ) -> list[BestPracticeViolation]:
        """Run all best practice rules against a single app registration."""
        violations: list[BestPracticeViolation] = []
        violations.extend(self._check_credential_expiry(tenant_id, app))
        violations.extend(self._check_app_no_owner(tenant_id, app))
        violations.extend(self._check_app_multi_tenant(tenant_id, app))
        violations.extend(self._check_app_excessive_permissions(tenant_id, app))
        return violations

    def _check_credential_expiry(
        self,
        tenant_id: str,
        app: AppRegistrationProfile,
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []
        all_creds = app.password_credentials + app.key_credentials

        for cred in all_creds:
            cred_label = f"{cred.credential_type} credential"
            if cred.is_expired:
                violations.append(self._build_app_violation(
                    tenant_id=tenant_id, app=app,
                    violation_type=ViolationType.SP_CREDENTIAL_EXPIRY,
                    priority=ViolationPriority.CRITICAL,
                    title=f"Expired {cred_label} on '{app.display_name}'",
                    description=f"App '{app.display_name}' has an expired {cred_label}. Remove it to reduce attack surface.",
                    id_suffix=f"cred_{cred.key_id}",
                ))
            elif cred.days_until_expiry is not None and cred.days_until_expiry <= 30:
                violations.append(self._build_app_violation(
                    tenant_id=tenant_id, app=app,
                    violation_type=ViolationType.SP_CREDENTIAL_EXPIRY,
                    priority=ViolationPriority.HIGH,
                    title=f"{cred_label.capitalize()} expires in {cred.days_until_expiry} days on '{app.display_name}'",
                    description=f"Rotate this credential before it expires to avoid service disruption.",
                    id_suffix=f"cred_{cred.key_id}",
                ))
            elif cred.days_until_expiry is not None and cred.days_until_expiry <= 90:
                violations.append(self._build_app_violation(
                    tenant_id=tenant_id, app=app,
                    violation_type=ViolationType.SP_CREDENTIAL_EXPIRY,
                    priority=ViolationPriority.MEDIUM,
                    title=f"{cred_label.capitalize()} expires in {cred.days_until_expiry} days on '{app.display_name}'",
                    description=f"Plan rotation for this credential on app '{app.display_name}'.",
                    id_suffix=f"cred_{cred.key_id}",
                ))
            elif cred.end_date_time is None:
                violations.append(self._build_app_violation(
                    tenant_id=tenant_id, app=app,
                    violation_type=ViolationType.SP_CREDENTIAL_EXPIRY,
                    priority=ViolationPriority.HIGH,
                    title=f"Non-expiring {cred_label} on '{app.display_name}'",
                    description=f"Credentials should have an expiry date. Set a maximum lifetime.",
                    id_suffix=f"cred_{cred.key_id}",
                ))

            if cred.credential_type == "password" and cred.age_days and cred.age_days > 365:
                violations.append(self._build_app_violation(
                    tenant_id=tenant_id, app=app,
                    violation_type=ViolationType.APP_STALE_CREDENTIAL,
                    priority=ViolationPriority.HIGH,
                    title=f"Password credential older than {cred.age_days} days on '{app.display_name}'",
                    description=f"Secrets should be rotated at least annually.",
                    id_suffix=f"stale_{cred.key_id}",
                ))

        return violations

    def _check_app_no_owner(
        self,
        tenant_id: str,
        app: AppRegistrationProfile,
    ) -> list[BestPracticeViolation]:
        if app.owner_count == 0:
            return [self._build_app_violation(
                tenant_id=tenant_id, app=app,
                violation_type=ViolationType.APP_NO_OWNER,
                priority=ViolationPriority.HIGH,
                title=f"No owner on app '{app.display_name}'",
                description="Orphaned app registrations have no accountability for credential rotation or access reviews.",
            )]
        return []

    def _check_app_multi_tenant(
        self,
        tenant_id: str,
        app: AppRegistrationProfile,
    ) -> list[BestPracticeViolation]:
        if not app.is_multi_tenant:
            return []
        if app.high_risk_permissions:
            return [self._build_app_violation(
                tenant_id=tenant_id, app=app,
                violation_type=ViolationType.APP_MULTI_TENANT,
                priority=ViolationPriority.CRITICAL if app.sign_in_audience == "AzureADandPersonalMicrosoftAccount" else ViolationPriority.HIGH,
                title=f"Multi-tenant app '{app.display_name}' with high-risk permissions",
                description=f"Multi-tenant app requests {', '.join(app.high_risk_permissions)}. Review whether multi-tenant access is necessary.",
            )]
        return []

    def _check_app_excessive_permissions(
        self,
        tenant_id: str,
        app: AppRegistrationProfile,
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []

        critical_perms = [
            p for p in app.requested_permissions
            if p.permission_type == "Role" and p.permission_id in HIGH_RISK_APP_PERMISSION_GUIDS
        ]
        if critical_perms:
            perm_names = [p.permission_value or p.permission_id for p in critical_perms]
            violations.append(self._build_app_violation(
                tenant_id=tenant_id, app=app,
                violation_type=ViolationType.APP_EXCESSIVE_PERMISSIONS,
                priority=ViolationPriority.CRITICAL,
                title=f"High-risk permissions on app '{app.display_name}'",
                description=f"App requests critical permissions: {', '.join(perm_names)}. These enable privilege escalation.",
            ))

        if app.total_app_permissions > 10:
            violations.append(self._build_app_violation(
                tenant_id=tenant_id, app=app,
                violation_type=ViolationType.APP_EXCESSIVE_PERMISSIONS,
                priority=ViolationPriority.HIGH,
                title=f"App '{app.display_name}' has {app.total_app_permissions} application permissions",
                description="Excessive application permissions increase blast radius. Apply least-privilege.",
                id_suffix="excessive_count",
            ))

        return violations

    # ------------------------------------------------------------------
    # MFA checks (Phase 1.3)
    # ------------------------------------------------------------------

    def evaluate_mfa(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        mfa_record: MfaRegistrationRecord | None,
    ) -> list[BestPracticeViolation]:
        if mfa_record is None:
            return []

        violations: list[BestPracticeViolation] = []
        is_admin = bool([
            r for r in identity.current_roles
            if "administrator" in r.role_name.lower() or "global" in r.role_name.lower()
        ])

        if not mfa_record.is_mfa_registered:
            violations.append(self._build_violation(
                tenant_id=tenant_id, identity=identity,
                violation_type=ViolationType.MFA_GAP,
                priority=ViolationPriority.CRITICAL if is_admin else ViolationPriority.HIGH,
                title="No MFA registered" + (" (admin)" if is_admin else ""),
                description=f"Identity '{identity.display_name}' has no MFA methods registered. This is a critical security gap.",
                remediation_steps=[
                    "Register at least one MFA method (FIDO2 or Authenticator app recommended).",
                    "Enforce MFA registration via Conditional Access policy.",
                ],
                affected_roles=[r.role_name for r in identity.current_roles],
                id_suffix="mfa_none",
            ))
            return violations

        methods = set(mfa_record.methods_registered)
        only_weak = methods and methods.issubset(WEAK_MFA_METHODS)
        if only_weak:
            violations.append(self._build_violation(
                tenant_id=tenant_id, identity=identity,
                violation_type=ViolationType.MFA_GAP,
                priority=ViolationPriority.HIGH,
                title="Only weak MFA methods (SMS/email)",
                description=f"Identity '{identity.display_name}' only has phishable MFA methods (SMS/email). Upgrade to phishing-resistant methods.",
                remediation_steps=[
                    "Register FIDO2 security key or Microsoft Authenticator.",
                    "Use authentication strength policies to require phishing-resistant MFA.",
                ],
                affected_roles=[r.role_name for r in identity.current_roles],
                id_suffix="mfa_weak",
            ))

        if is_admin and not (methods & PHISHING_RESISTANT_METHODS):
            violations.append(self._build_violation(
                tenant_id=tenant_id, identity=identity,
                violation_type=ViolationType.MFA_GAP,
                priority=ViolationPriority.HIGH,
                title="Admin without phishing-resistant MFA",
                description=f"Admin '{identity.display_name}' lacks FIDO2/WHfB/certificate auth. Admins should use phishing-resistant methods.",
                remediation_steps=[
                    "Register a FIDO2 security key or Windows Hello for Business.",
                    "Enforce phishing-resistant MFA via authentication strength policy.",
                ],
                affected_roles=[r.role_name for r in identity.current_roles],
                id_suffix="mfa_admin_no_pr",
            ))

        return violations

    # ------------------------------------------------------------------
    # Guest checks (Phase 2.4)
    # ------------------------------------------------------------------

    def evaluate_guest(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        mfa_record: MfaRegistrationRecord | None = None,
    ) -> list[BestPracticeViolation]:
        if identity.user_type != "Guest":
            return []

        violations: list[BestPracticeViolation] = []

        admin_roles = [
            r for r in identity.current_roles
            if "administrator" in r.role_name.lower() or "global" in r.role_name.lower()
        ]
        if admin_roles:
            violations.append(self._build_violation(
                tenant_id=tenant_id, identity=identity,
                violation_type=ViolationType.GUEST_ADMIN,
                priority=ViolationPriority.CRITICAL,
                title=f"Guest user with admin roles",
                description=f"Guest '{identity.display_name}' holds admin roles: {', '.join(r.role_name for r in admin_roles)}. Guests should not have privileged access.",
                remediation_steps=[
                    "Remove admin roles from guest accounts.",
                    "Convert to a member account if admin access is required.",
                ],
                affected_roles=[r.role_name for r in admin_roles],
            ))

        if identity.external_user_state == "PendingAcceptance":
            now = datetime.now(UTC)
            if identity.first_seen and (now - identity.first_seen).days > 30:
                violations.append(self._build_violation(
                    tenant_id=tenant_id, identity=identity,
                    violation_type=ViolationType.GUEST_PENDING_INVITATION,
                    priority=ViolationPriority.MEDIUM,
                    title="Pending guest invitation > 30 days",
                    description=f"Guest '{identity.display_name}' has not accepted the invitation for over 30 days.",
                    remediation_steps=[
                        "Resend the invitation or remove the guest account.",
                    ],
                    affected_roles=[],
                ))

        if identity.last_seen:
            now = datetime.now(UTC)
            last_seen = identity.last_seen
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)
            if (now - last_seen).days > 90:
                violations.append(self._build_violation(
                    tenant_id=tenant_id, identity=identity,
                    violation_type=ViolationType.GUEST_STALE,
                    priority=ViolationPriority.HIGH,
                    title=f"Stale guest user (inactive > 90 days)",
                    description=f"Guest '{identity.display_name}' has not signed in for over 90 days. Remove stale guest access.",
                    remediation_steps=[
                        "Remove the guest account if the collaboration has ended.",
                        "Set up access reviews for guest users.",
                    ],
                    affected_roles=[r.role_name for r in identity.current_roles],
                ))

        if mfa_record and not mfa_record.is_mfa_registered:
            violations.append(self._build_violation(
                tenant_id=tenant_id, identity=identity,
                violation_type=ViolationType.GUEST_NO_MFA,
                priority=ViolationPriority.MEDIUM,
                title="Guest user without MFA",
                description=f"Guest '{identity.display_name}' has no MFA registered. Enforce MFA for guests via Conditional Access.",
                remediation_steps=[
                    "Create a CA policy requiring MFA for guest/external users.",
                ],
                affected_roles=[],
            ))

        return violations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_app_violation(
        *,
        tenant_id: str,
        app: AppRegistrationProfile,
        violation_type: ViolationType,
        priority: ViolationPriority,
        title: str,
        description: str,
        id_suffix: str | None = None,
    ) -> BestPracticeViolation:
        suffix = id_suffix or violation_type.value
        doc_id = f"app_{app.id}_{suffix}"
        return BestPracticeViolation(
            id=doc_id,
            tenant_id=tenant_id,
            identity_id=f"app_{app.id}",
            identity_display_name=app.display_name,
            identity_type="Application",
            violation_type=violation_type,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=[],
            affected_roles=[],
            detected_at=datetime.now(UTC),
        )

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
