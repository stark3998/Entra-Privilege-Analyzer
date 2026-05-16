from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.models.action import ActionEvent
from app.models.pim_session import (
    PimSession,
    PimSessionAnomaly,
    PimSessionAnomalyType,
    SessionLocationInfo,
)
logger = logging.getLogger(__name__)

_HIGH_PRIVILEGE_ROLES = {
    "Global Administrator",
    "Privileged Role Administrator",
    "Privileged Authentication Administrator",
    "Security Administrator",
    "Exchange Administrator",
    "SharePoint Administrator",
    "User Administrator",
    "Application Administrator",
}

_SENSITIVE_ACTIONS = {
    "Add member to role",
    "Add eligible member to role",
    "Remove member from role",
    "Update application – Certificates and secrets management",
    "Update conditional access policy",
    "Add owner to application",
    "Consent to application",
    "Update policy",
    "Add app role assignment to service principal",
    "Reset user password",
    "Delete user",
    "Update user",
    "Invite external user",
}


class PimSessionAnomalyDetector:
    """Detects anomalies in PIM privileged sessions."""

    def __init__(
        self,
        repo: Any,
        business_hours_start: int = 7,
        business_hours_end: int = 19,
    ) -> None:
        self._repo = repo
        self._bh_start = business_hours_start
        self._bh_end = business_hours_end

    async def detect(
        self,
        tenant_id: str,
        session: PimSession,
        session_audit_events: list[ActionEvent],
        sign_in_raw: list[dict[str, Any]],
    ) -> list[PimSessionAnomaly]:
        now = datetime.now(UTC)
        anomalies: list[PimSessionAnomaly] = []

        anomalies.extend(self._check_unusual_time(session, now))
        anomalies.extend(self._check_no_justification(session, now))
        anomalies.extend(self._check_sensitive_actions(session_audit_events, now))
        anomalies.extend(await self._check_first_time_role(tenant_id, session, now))
        anomalies.extend(self._check_new_location(session, sign_in_raw, now))
        anomalies.extend(
            await self._check_high_volume(tenant_id, session, session_audit_events, now)
        )

        return anomalies

    def _check_unusual_time(
        self,
        session: PimSession,
        now: datetime,
    ) -> list[PimSessionAnomaly]:
        hour = session.activation_time.hour
        weekday = session.activation_time.weekday()

        if weekday >= 5:
            return [
                PimSessionAnomaly(
                    anomaly_type=PimSessionAnomalyType.UNUSUAL_ACTIVATION_TIME,
                    severity="high",
                    details=f"Role activated on a weekend ({session.activation_time.strftime('%A')}).",
                    detected_at=now,
                )
            ]

        if hour < self._bh_start or hour >= self._bh_end:
            return [
                PimSessionAnomaly(
                    anomaly_type=PimSessionAnomalyType.UNUSUAL_ACTIVATION_TIME,
                    severity="medium",
                    details=(
                        f"Role activated outside business hours "
                        f"({session.activation_time.strftime('%H:%M')} UTC, "
                        f"business hours: {self._bh_start:02d}:00-{self._bh_end:02d}:00)."
                    ),
                    detected_at=now,
                )
            ]

        return []

    def _check_no_justification(
        self,
        session: PimSession,
        now: datetime,
    ) -> list[PimSessionAnomaly]:
        if session.justification:
            return []
        if session.role_name not in _HIGH_PRIVILEGE_ROLES:
            return []
        return [
            PimSessionAnomaly(
                anomaly_type=PimSessionAnomalyType.NO_JUSTIFICATION,
                severity="medium",
                details=(
                    f"High-privilege role '{session.role_name}' activated "
                    f"without providing a justification."
                ),
                detected_at=now,
            )
        ]

    def _check_sensitive_actions(
        self,
        events: list[ActionEvent],
        now: datetime,
    ) -> list[PimSessionAnomaly]:
        found = [e.action for e in events if e.action in _SENSITIVE_ACTIONS]
        if not found:
            return []
        unique = sorted(set(found))
        return [
            PimSessionAnomaly(
                anomaly_type=PimSessionAnomalyType.SENSITIVE_ACTION,
                severity="high",
                details=(
                    f"Sensitive actions performed during session: {', '.join(unique[:5])}"
                    + (f" (+{len(unique) - 5} more)" if len(unique) > 5 else "")
                    + "."
                ),
                detected_at=now,
            )
        ]

    async def _check_first_time_role(
        self,
        tenant_id: str,
        session: PimSession,
        now: datetime,
    ) -> list[PimSessionAnomaly]:
        existing, _ = await self._repo.list_pim_sessions(
            principal_id=session.principal_id,
            role_name=session.role_name,
            limit=1,
        )
        prior = [s for s in existing if s.id != session.id]
        if prior:
            return []

        severity = "critical" if session.role_name in _HIGH_PRIVILEGE_ROLES else "medium"
        return [
            PimSessionAnomaly(
                anomaly_type=PimSessionAnomalyType.FIRST_TIME_ROLE,
                severity=severity,
                details=(
                    f"First-time activation of '{session.role_name}' "
                    f"by {session.principal_display_name}."
                ),
                detected_at=now,
            )
        ]

    def _check_new_location(
        self,
        session: PimSession,
        sign_in_raw: list[dict[str, Any]],
        now: datetime,
    ) -> list[PimSessionAnomaly]:
        session_countries: set[str] = set()
        for si in sign_in_raw:
            loc = si.get("location") or {}
            country = loc.get("countryOrRegion")
            if country:
                session_countries.add(country)

        if not session_countries:
            return []

        known_countries: set[str] = set()
        for loc_info in session.locations or []:
            if loc_info.country:
                known_countries.add(loc_info.country)

        new_countries = session_countries - known_countries
        if not new_countries or not known_countries:
            return []

        return [
            PimSessionAnomaly(
                anomaly_type=PimSessionAnomalyType.NEW_LOCATION,
                severity="high",
                details=(
                    f"Sign-in from new country/region during session: "
                    f"{', '.join(sorted(new_countries))}."
                ),
                detected_at=now,
            )
        ]

    async def _check_high_volume(
        self,
        tenant_id: str,
        session: PimSession,
        events: list[ActionEvent],
        now: datetime,
    ) -> list[PimSessionAnomaly]:
        current_count = len(events)
        if current_count < 5:
            return []

        historical, _ = await self._repo.list_pim_sessions(
            principal_id=session.principal_id,
            limit=20,
        )
        prior = [s for s in historical if s.id != session.id and s.total_event_count > 0]
        if len(prior) < 3:
            return []

        counts = [s.total_event_count for s in prior]
        mean = sum(counts) / len(counts)
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        stddev = variance**0.5

        if stddev == 0:
            return []

        z_score = (current_count - mean) / stddev
        if z_score <= 2.0:
            return []

        severity = "high" if z_score > 3.0 else "medium"
        return [
            PimSessionAnomaly(
                anomaly_type=PimSessionAnomalyType.HIGH_VOLUME_ACTIONS,
                severity=severity,
                details=(
                    f"Unusually high activity during session: {current_count} events "
                    f"(z-score {z_score:.1f}, mean {mean:.1f}, stddev {stddev:.1f})."
                ),
                detected_at=now,
            )
        ]


def compute_risk_score(anomalies: list[PimSessionAnomaly]) -> float:
    weights = {"critical": 10, "high": 7, "medium": 3, "low": 1}
    total = sum(weights.get(a.severity, 0) for a in anomalies)
    return min(total, 100.0)


def extract_locations(sign_in_raw: list[dict[str, Any]]) -> list[SessionLocationInfo]:
    seen: set[str] = set()
    locations: list[SessionLocationInfo] = []
    for si in sign_in_raw:
        ip = si.get("ipAddress")
        key = ip or ""
        if key in seen:
            continue
        seen.add(key)
        loc = si.get("location") or {}
        geo = loc.get("geoCoordinates") or {}
        locations.append(
            SessionLocationInfo(
                ip_address=ip,
                city=loc.get("city"),
                state=loc.get("state"),
                country=loc.get("countryOrRegion"),
                latitude=geo.get("latitude"),
                longitude=geo.get("longitude"),
            )
        )
    return locations
