# backend/app/services/risk_scorer.py
"""Composite risk scoring for identities based on drift, privilege, and staleness."""
from __future__ import annotations

from datetime import UTC, datetime

from app.models.drift import DriftAlert, DriftSeverity
from app.models.identity import IdentityProfile
from app.models.role import PermissionGap

# Severity weights for drift alert scoring
_SEVERITY_WEIGHTS: dict[DriftSeverity, float] = {
    DriftSeverity.CRITICAL: 4.0,
    DriftSeverity.HIGH: 3.0,
    DriftSeverity.MEDIUM: 2.0,
    DriftSeverity.LOW: 1.0,
}

# Role name patterns that indicate high-privilege admin
_HIGH_PRIV_PATTERNS = (
    "global administrator",
    "privileged role administrator",
    "privileged authentication administrator",
    "security administrator",
)

# Maximum expected drift score for normalisation (cap)
_MAX_DRIFT_RAW = 20.0

# Days thresholds for stale access scoring
_STALE_THRESHOLD_DAYS = 30


class RiskScorer:
    """Computes a composite risk score (0-100) for an identity."""

    def compute_risk_score(
        self,
        identity: IdentityProfile,
        drift_alerts: list[DriftAlert],
        permission_gaps: list[PermissionGap],
    ) -> float:
        """Return a weighted composite score (0-100).

        Components (weights):
        - 20%: active drift alerts (count * severity weight, normalised)
        - 20%: overprivilege (gap count / total permissions * 100)
        - 15%: permanent admin roles (permanent + high-privilege role names)
        - 15%: stale access (days since last_seen > 30 -> escalating score)
        - 20%: identity protection (Entra ID risk level + risk detections)
        - 10%: guest / B2B risk (pending guests, admin guests, no access review)
        """
        drift_score = self._drift_component(drift_alerts)
        overpriv_score = self._overprivilege_component(identity, permission_gaps)
        admin_score = self._permanent_admin_component(identity)
        stale_score = self._stale_access_component(identity)
        idp_score = self._identity_protection_component(identity)
        guest_score = self._guest_b2b_component(identity)

        composite = (
            0.20 * drift_score
            + 0.20 * overpriv_score
            + 0.15 * admin_score
            + 0.15 * stale_score
            + 0.20 * idp_score
            + 0.10 * guest_score
        )

        return round(min(max(composite, 0.0), 100.0), 2)

    def _drift_component(self, alerts: list[DriftAlert]) -> float:
        """Score from active (non-resolved) drift alerts."""
        raw = sum(
            _SEVERITY_WEIGHTS.get(a.severity, 1.0)
            for a in alerts
            if a.status != "resolved"
        )
        # Normalise: raw / _MAX_DRIFT_RAW * 100, capped at 100
        return min(raw / _MAX_DRIFT_RAW * 100.0, 100.0)

    def _overprivilege_component(
        self,
        identity: IdentityProfile,
        gaps: list[PermissionGap],
    ) -> float:
        """Score from unused permissions relative to total assigned."""
        total_perms = len(identity.current_roles) + len(gaps)
        if total_perms == 0:
            return 0.0
        return min(len(gaps) / max(total_perms, 1) * 100.0, 100.0)

    def _permanent_admin_component(self, identity: IdentityProfile) -> float:
        """Score from permanent high-privilege admin roles."""
        score = 0.0
        for role in identity.current_roles:
            if not role.is_permanent:
                continue
            name_lower = role.role_name.lower()
            if any(p in name_lower for p in _HIGH_PRIV_PATTERNS):
                score += 50.0  # High-privilege permanent role
            elif "administrator" in name_lower:
                score += 25.0  # Other admin permanent role
            elif role.is_permanent:
                score += 5.0  # Any permanent role adds minor risk
        return min(score, 100.0)

    def _stale_access_component(self, identity: IdentityProfile) -> float:
        """Escalating score based on days since last activity."""
        if identity.last_seen is None:
            return 100.0  # Never seen -> maximum stale risk

        now = datetime.now(UTC)
        last_seen = identity.last_seen
        # Ensure timezone-aware comparison
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)

        days_inactive = (now - last_seen).days

        if days_inactive <= _STALE_THRESHOLD_DAYS:
            return 0.0
        if days_inactive <= 60:
            return 30.0
        if days_inactive <= 90:
            return 60.0
        return 100.0

    def _identity_protection_component(self, identity: IdentityProfile) -> float:
        """Score from Entra ID Identity Protection risk signals."""
        if identity.entra_risk_state == "confirmedCompromised":
            return 100.0

        risk_level_map: dict[str, float] = {
            "high": 100.0,
            "medium": 60.0,
            "low": 30.0,
            "none": 0.0,
        }
        base = risk_level_map.get(identity.entra_risk_level or "none", 0.0)

        if identity.entra_risk_state == "atRisk":
            base = max(base, 70.0)

        high_risk_event_types = {
            "leakedCredentials",
            "passwordSpray",
            "suspiciousAPITraffic",
            "anomalousToken",
        }
        for detection in identity.active_risk_detections:
            if detection.risk_event_type in high_risk_event_types:
                base += 15.0

        return min(base, 100.0)

    def _guest_b2b_component(self, identity: IdentityProfile) -> float:
        """Score from guest / B2B collaboration risk factors."""
        if identity.user_type != "Guest":
            return 0.0

        score = 20.0  # Baseline for any guest

        if identity.external_user_state == "PendingAcceptance":
            score += 30.0

        for role in identity.current_roles:
            name_lower = role.role_name.lower()
            if "administrator" in name_lower or "global" in name_lower:
                score += 40.0
                break

        if not identity.covered_by_access_review:
            score += 10.0

        return min(score, 100.0)
