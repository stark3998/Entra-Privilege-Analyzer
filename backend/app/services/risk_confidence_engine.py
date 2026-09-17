from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.governance import RiskAssessment, ScoreComponent
from app.models.identity import IdentityProfile

_SCORECARD_VERSION = "2026-09-01"


class RiskConfidenceEngine:
    """Produces explainable risk, impact, confidence, and completeness scores."""

    def assess(
        self,
        identity: IdentityProfile,
        *,
        drift_score: float,
        unused_permission_ratio: float,
        peer_deviation: float,
        seasonal_deviation: float,
        evidence_coverage: float,
        evidence_days: int,
        evidence_ids: list[str] | None = None,
    ) -> RiskAssessment:
        ids = evidence_ids or []
        components = [
            ScoreComponent(
                name="drift",
                value=_bounded(drift_score),
                weight=0.30,
                evidence_ids=ids,
                explanation="Active anomalous or first-seen behavior.",
            ),
            ScoreComponent(
                name="unused_privilege",
                value=_bounded(unused_permission_ratio * 100),
                weight=0.30,
                evidence_ids=ids,
                explanation="Assigned permissions without observed use.",
            ),
            ScoreComponent(
                name="peer_deviation",
                value=_bounded(peer_deviation),
                weight=0.20,
                evidence_ids=ids,
                explanation="Deviation from comparable identities.",
            ),
            ScoreComponent(
                name="seasonal_deviation",
                value=_bounded(seasonal_deviation),
                weight=0.20,
                evidence_ids=ids,
                explanation="Deviation from the identity's seasonal baseline.",
            ),
        ]
        risk = sum(component.value * component.weight for component in components)
        privileged = sum(1 for role in identity.current_roles if role.is_permanent)
        high_impact = sum(
            1
            for role in identity.current_roles
            if "administrator" in role.role_name.lower() or "owner" in role.role_name.lower()
        )
        impact = _bounded(privileged * 8 + high_impact * 22)
        completeness = min(max(evidence_coverage, 0.0), 1.0)
        window_factor = min(max(evidence_days / 90, 0.0), 1.0)
        confidence = round(completeness * window_factor, 4)
        return RiskAssessment(
            id=str(uuid.uuid4()),
            tenant_id=identity.tenant_id,
            identity_id=identity.id,
            scorecard_version=_SCORECARD_VERSION,
            risk=round(risk, 2),
            impact=round(impact, 2),
            confidence=confidence,
            completeness=round(completeness, 4),
            components=components,
            seasonal_anomaly=seasonal_deviation >= 70,
            computed_at=datetime.now(UTC),
        )


def _bounded(value: float) -> float:
    return min(max(value, 0.0), 100.0)
