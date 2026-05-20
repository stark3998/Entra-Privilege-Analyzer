"""B4: Analyzes workload identity federation credentials for misconfigurations."""

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

_BROAD_SUBJECT_PATTERNS: list[str] = [
    "*",
    "repo:*",
    "ref:refs/*",
    "environment:*",
]


class FederationAnalyzer:
    """Evaluates federated identity credentials for overly broad configurations."""

    def evaluate_federated_credentials(
        self,
        tenant_id: str,
        app_id: str,
        app_display_name: str,
        credentials: list[dict[str, Any]],
    ) -> list[BestPracticeViolation]:
        violations: list[BestPracticeViolation] = []

        for cred in credentials:
            name = cred.get("name", "unnamed")
            subject = cred.get("subject", "")
            issuer = cred.get("issuer", "")
            audiences = cred.get("audiences", [])

            violations.extend(
                self._check_broad_subject(
                    tenant_id, app_id, app_display_name, name, subject, issuer,
                )
            )
            violations.extend(
                self._check_audience(
                    tenant_id, app_id, app_display_name, name, audiences,
                )
            )

        return violations

    def _check_broad_subject(
        self,
        tenant_id: str,
        app_id: str,
        app_display_name: str,
        cred_name: str,
        subject: str,
        issuer: str,
    ) -> list[BestPracticeViolation]:
        if not subject:
            return [
                self._build(
                    tenant_id=tenant_id,
                    app_id=app_id,
                    violation_type=ViolationType.FEDERATION_BROAD_SUBJECT,
                    priority=ViolationPriority.CRITICAL,
                    title=f"Empty subject on federated credential '{cred_name}' for app '{app_display_name}'",
                    description=(
                        f"Federated credential '{cred_name}' on app '{app_display_name}' "
                        f"has no subject filter. Any token from issuer '{issuer}' will be accepted."
                    ),
                    id_suffix=f"fed_{cred_name}_no_subject",
                )
            ]

        is_broad = any(
            subject == pattern or subject.endswith(pattern.lstrip("*"))
            for pattern in _BROAD_SUBJECT_PATTERNS
            if pattern != "*"
        )
        if subject == "*":
            is_broad = True

        if not is_broad:
            return []

        return [
            self._build(
                tenant_id=tenant_id,
                app_id=app_id,
                violation_type=ViolationType.FEDERATION_BROAD_SUBJECT,
                priority=ViolationPriority.HIGH,
                title=f"Broad subject '{subject}' on federated credential for '{app_display_name}'",
                description=(
                    f"Federated credential '{cred_name}' on app '{app_display_name}' "
                    f"uses broad subject filter '{subject}'. This allows more "
                    "workloads than intended to authenticate as this app."
                ),
                id_suffix=f"fed_{cred_name}_broad",
            )
        ]

    def _check_audience(
        self,
        tenant_id: str,
        app_id: str,
        app_display_name: str,
        cred_name: str,
        audiences: list[str],
    ) -> list[BestPracticeViolation]:
        if audiences:
            return []

        return [
            self._build(
                tenant_id=tenant_id,
                app_id=app_id,
                violation_type=ViolationType.FEDERATION_NO_AUDIENCE,
                priority=ViolationPriority.MEDIUM,
                title=f"No audience restriction on federated credential for '{app_display_name}'",
                description=(
                    f"Federated credential '{cred_name}' on app '{app_display_name}' "
                    "has no audience restriction. Set the audience to "
                    "'api://AzureADTokenExchange' to prevent token misuse."
                ),
                id_suffix=f"fed_{cred_name}_no_audience",
            )
        ]

    @staticmethod
    def _build(
        *,
        tenant_id: str,
        app_id: str,
        violation_type: ViolationType,
        priority: ViolationPriority,
        title: str,
        description: str,
        id_suffix: str,
    ) -> BestPracticeViolation:
        return BestPracticeViolation(
            id=f"app_{app_id}_{id_suffix}",
            tenant_id=tenant_id,
            identity_id=f"app_{app_id}",
            identity_display_name="App Registration",
            identity_type="Application",
            violation_type=violation_type,
            priority=priority,
            title=title,
            description=description,
            remediation_steps=[
                "Narrow the subject filter to the specific repo/branch/environment.",
                "Set audience to 'api://AzureADTokenExchange'.",
                "Review whether federated credential is still needed.",
            ],
            affected_roles=[],
            detected_at=datetime.now(UTC),
        )
