# backend/app/services/access_review_analyzer.py
"""Evaluates access review coverage gaps and produces best practice violations."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.access_review import AccessReviewDefinition
from app.models.best_practice import (
    BestPracticeViolation,
    ViolationPriority,
    ViolationType,
)

_STALE_REVIEW_DAYS = 180  # 6 months


class AccessReviewAnalyzer:
    """Checks tenant access review coverage and freshness."""

    def evaluate_coverage(
        self,
        tenant_id: str,
        reviews: list[AccessReviewDefinition],
        privileged_role_ids: set[str],
        role_assignable_group_ids: set[str],
        has_guest_users: bool,
    ) -> list[BestPracticeViolation]:
        """Return violations for access review gaps."""
        violations: list[BestPracticeViolation] = []

        violations.extend(self._check_privileged_roles(tenant_id, reviews, privileged_role_ids))
        violations.extend(
            self._check_role_assignable_groups(tenant_id, reviews, role_assignable_group_ids)
        )
        violations.extend(self._check_stale_reviews(tenant_id, reviews))
        violations.extend(self._check_guest_review(tenant_id, reviews, has_guest_users))

        return violations

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_privileged_roles(
        self,
        tenant_id: str,
        reviews: list[AccessReviewDefinition],
        privileged_role_ids: set[str],
    ) -> list[BestPracticeViolation]:
        if not privileged_role_ids:
            return []

        covered_ids: set[str] = set()
        for review in reviews:
            if review.scope_type == "role" and review.target_resource_id:
                covered_ids.add(review.target_resource_id)
            # Also check scope_query for role IDs
            for role_id in privileged_role_ids:
                if role_id in review.scope_query:
                    covered_ids.add(role_id)

        uncovered = privileged_role_ids - covered_ids
        if not uncovered:
            return []

        return [
            self._build(
                tenant_id=tenant_id,
                priority=ViolationPriority.HIGH,
                title=f"{len(uncovered)} privileged role(s) without access review",
                description=(
                    f"No access review covers {len(uncovered)} privileged role assignment(s). "
                    "Periodic certification is required for privileged access."
                ),
                remediation_steps=[
                    "Create access reviews for all privileged Entra ID roles.",
                    "Set recurring quarterly cadence with auto-apply.",
                ],
                affected_roles=sorted(uncovered),
                id_suffix="no_access_review_roles",
            )
        ]

    def _check_role_assignable_groups(
        self,
        tenant_id: str,
        reviews: list[AccessReviewDefinition],
        role_assignable_group_ids: set[str],
    ) -> list[BestPracticeViolation]:
        if not role_assignable_group_ids:
            return []

        covered_ids: set[str] = set()
        for review in reviews:
            if review.scope_type == "group" and review.target_resource_id:
                covered_ids.add(review.target_resource_id)
            for group_id in role_assignable_group_ids:
                if group_id in review.scope_query:
                    covered_ids.add(group_id)

        uncovered = role_assignable_group_ids - covered_ids
        if not uncovered:
            return []

        return [
            self._build(
                tenant_id=tenant_id,
                priority=ViolationPriority.MEDIUM,
                title=f"{len(uncovered)} role-assignable group(s) without access review",
                description=(
                    f"{len(uncovered)} role-assignable group(s) lack access reviews. "
                    "Membership in these groups grants privileged roles."
                ),
                remediation_steps=[
                    "Create access reviews for each role-assignable group.",
                    "Ensure group owners or designated reviewers certify membership.",
                ],
                affected_roles=sorted(uncovered),
                id_suffix="no_access_review_groups",
            )
        ]

    def _check_stale_reviews(
        self,
        tenant_id: str,
        reviews: list[AccessReviewDefinition],
    ) -> list[BestPracticeViolation]:
        now = datetime.now(UTC)
        violations: list[BestPracticeViolation] = []

        for review in reviews:
            if review.status != "Completed":
                continue
            if review.recurrence_pattern is not None:
                continue
            if review.last_instance_end is None:
                continue

            end = review.last_instance_end
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)

            days_since = (now - end).days
            if days_since <= _STALE_REVIEW_DAYS:
                continue

            violations.append(
                self._build(
                    tenant_id=tenant_id,
                    priority=ViolationPriority.MEDIUM,
                    title=f"Stale access review '{review.display_name}' ({days_since}d ago)",
                    description=(
                        f"Access review '{review.display_name}' completed {days_since} days ago "
                        "with no recurrence configured. Reviews should recur at least every 6 months."
                    ),
                    remediation_steps=[
                        f"Edit review '{review.display_name}' and enable recurring schedule.",
                        "Recommended cadence: quarterly for privileged roles, semi-annually for others.",
                    ],
                    affected_roles=[],
                    id_suffix=f"stale_review_{review.id}",
                )
            )

        return violations

    def _check_guest_review(
        self,
        tenant_id: str,
        reviews: list[AccessReviewDefinition],
        has_guest_users: bool,
    ) -> list[BestPracticeViolation]:
        if not has_guest_users:
            return []

        for review in reviews:
            scope_lower = review.scope_query.lower()
            if "guest" in scope_lower:
                return []
            if review.scope_type.lower() == "guest":
                return []

        return [
            self._build(
                tenant_id=tenant_id,
                priority=ViolationPriority.HIGH,
                title="No access review for guest users",
                description=(
                    "Tenant has guest users but no access review scoped to guests. "
                    "Guest access should be periodically certified."
                ),
                remediation_steps=[
                    "Create an access review scoped to guest/external users.",
                    "Set quarterly recurrence with auto-removal on denial.",
                ],
                affected_roles=[],
                id_suffix="no_guest_review",
            )
        ]

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _build(
        *,
        tenant_id: str,
        priority: ViolationPriority,
        title: str,
        description: str,
        remediation_steps: list[str],
        affected_roles: list[str],
        id_suffix: str,
    ) -> BestPracticeViolation:
        identity_id = f"tenant_{tenant_id}"
        return BestPracticeViolation(
            id=f"{identity_id}_{id_suffix}",
            tenant_id=tenant_id,
            identity_id=identity_id,
            identity_display_name="Tenant",
            identity_type="Tenant",
            violation_type=ViolationType.OVERPRIVILEGED,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=remediation_steps,
            affected_roles=affected_roles,
            detected_at=datetime.now(UTC),
        )
