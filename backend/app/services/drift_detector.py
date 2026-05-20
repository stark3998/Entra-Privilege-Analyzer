# backend/app/services/drift_detector.py
"""Two-layer permission drift detection: first-seen and frequency anomaly."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from datetime import UTC, datetime

from app.data.permission_catalog import action_to_permission, get_risk_weight_numeric
from app.models.drift import (
    BaselineStats,
    DriftAlert,
    DriftSeverity,
    DriftStatus,
    DriftType,
)
from app.models.identity import IdentityProfile

logger = logging.getLogger(__name__)

# Minimum baseline samples before z-score detection activates
_MIN_SAMPLES = 7

# Z-score thresholds for frequency anomaly severity
_Z_HIGH = 3.0
_Z_MEDIUM = 2.0
_Z_LOW = 1.5


def _severity_from_risk_weight(weight: int) -> DriftSeverity:
    """Map a numeric risk weight to a drift severity."""
    if weight >= 10:
        return DriftSeverity.CRITICAL
    if weight >= 7:
        return DriftSeverity.HIGH
    if weight >= 3:
        return DriftSeverity.MEDIUM
    return DriftSeverity.LOW


def _severity_from_z_score(z: float) -> DriftSeverity:
    """Map a z-score to a drift severity."""
    if z > _Z_HIGH:
        return DriftSeverity.HIGH
    if z > _Z_MEDIUM:
        return DriftSeverity.MEDIUM
    return DriftSeverity.LOW


class DriftDetector:
    """Detects permission drift via first-seen actions and frequency anomalies."""

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    async def detect_first_seen(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        baseline_actions: set[str],
    ) -> list[DriftAlert]:
        """Flag any observed action NOT in the baseline set.

        Severity derives from the action's risk weight in the permission catalog.
        """
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        for observed in identity.observed_actions:
            if observed.action in baseline_actions:
                continue

            # Look up risk weight via permission catalog
            permission = action_to_permission(observed.action)
            weight = get_risk_weight_numeric(permission) if permission else 1
            severity = _severity_from_risk_weight(weight)

            alert = DriftAlert(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                identity_id=identity.id,
                identity_display_name=identity.display_name,
                drift_type=DriftType.FIRST_SEEN,
                action=observed.action,
                resource=observed.resource,
                severity=severity,
                status=DriftStatus.OPEN,
                details=(
                    f"Action '{observed.action}' was observed for the first time. "
                    f"Not present in the rolling baseline."
                ),
                detected_at=now,
            )
            alerts.append(alert)

        return alerts

    async def detect_frequency_anomaly(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        baselines: list[BaselineStats],
    ) -> list[DriftAlert]:
        """Flag actions whose observed count deviates significantly from baseline.

        Only applies when the baseline has at least ``_MIN_SAMPLES`` data points
        and a non-zero standard deviation.
        """
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        # Build lookup: (action, resource) -> BaselineStats
        baseline_map: dict[tuple[str, str | None], BaselineStats] = {
            (b.action, b.resource): b for b in baselines
        }

        for observed in identity.observed_actions:
            key = (observed.action, observed.resource)
            baseline = baseline_map.get(key)

            if baseline is None or baseline.sample_count < _MIN_SAMPLES:
                continue

            if baseline.stddev == 0:
                continue

            z = (observed.count - baseline.mean) / baseline.stddev

            if z < _Z_LOW:
                continue

            severity = _severity_from_z_score(z)
            alert = DriftAlert(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                identity_id=identity.id,
                identity_display_name=identity.display_name,
                drift_type=DriftType.FREQUENCY_ANOMALY,
                action=observed.action,
                resource=observed.resource,
                severity=severity,
                status=DriftStatus.OPEN,
                z_score=round(z, 4),
                baseline_mean=round(baseline.mean, 4),
                baseline_stddev=round(baseline.stddev, 4),
                observed_count=observed.count,
                details=(
                    f"Action '{observed.action}' count ({observed.count}) deviates "
                    f"from baseline (mean={baseline.mean:.2f}, "
                    f"stddev={baseline.stddev:.2f}, z={z:.2f})."
                ),
                detected_at=now,
            )
            alerts.append(alert)

        return alerts

    async def detect_temporal_anomaly(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        baselines: list[BaselineStats],
    ) -> list[DriftAlert]:
        """A1: Flag actions occurring outside the identity's normal working hours."""
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        baseline_histograms: dict[str, list[int]] = {}
        for b in baselines:
            if b.hour_histogram and len(b.hour_histogram) == 24:
                baseline_histograms[b.action] = b.hour_histogram

        if not baseline_histograms:
            return alerts

        total_hist = [0] * 24
        for hist in baseline_histograms.values():
            for i in range(24):
                total_hist[i] += hist[i]

        total_events = sum(total_hist) or 1
        hour_fractions = [h / total_events for h in total_hist]
        mean_frac = sum(hour_fractions) / 24
        variance = sum((f - mean_frac) ** 2 for f in hour_fractions) / 24
        stddev_frac = variance**0.5

        if stddev_frac == 0:
            return alerts

        for observed in identity.observed_actions:
            hour = observed.last_seen.hour
            frac = hour_fractions[hour]
            if frac < mean_frac - 2 * stddev_frac and total_hist[hour] < 3:
                permission = action_to_permission(observed.action)
                weight = get_risk_weight_numeric(permission) if permission else 1
                severity = _severity_from_risk_weight(weight)

                alert = DriftAlert(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    identity_id=identity.id,
                    identity_display_name=identity.display_name,
                    drift_type=DriftType.TEMPORAL_ANOMALY,
                    action=observed.action,
                    resource=observed.resource,
                    severity=severity,
                    status=DriftStatus.OPEN,
                    hour_of_day=hour,
                    details=(
                        f"Action '{observed.action}' at hour {hour:02d}:00 UTC "
                        f"is outside normal activity pattern for this identity."
                    ),
                    detected_at=now,
                )
                alerts.append(alert)

        return alerts

    async def detect_velocity_anomaly(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        baselines: list[BaselineStats],
    ) -> list[DriftAlert]:
        """A3: Flag identities with action bursts exceeding baseline rate."""
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        if not baselines:
            return alerts

        total_baseline_mean = sum(b.mean for b in baselines)
        total_baseline_stddev = sum(b.stddev for b in baselines)

        if total_baseline_mean == 0:
            return alerts

        recent_actions = [
            oa for oa in identity.observed_actions
            if (now - oa.last_seen).total_seconds() < 3600
        ]
        recent_count = sum(oa.count for oa in recent_actions)

        hourly_baseline = total_baseline_mean / 24
        if hourly_baseline == 0:
            hourly_baseline = 1.0

        velocity_ratio = recent_count / hourly_baseline

        if velocity_ratio < 3.0:
            return alerts

        if velocity_ratio > 10:
            severity = DriftSeverity.CRITICAL
        elif velocity_ratio > 5:
            severity = DriftSeverity.HIGH
        else:
            severity = DriftSeverity.MEDIUM

        high_risk_actions = [
            oa.action for oa in recent_actions
            if action_to_permission(oa.action) and get_risk_weight_numeric(action_to_permission(oa.action)) >= 7
        ]
        if high_risk_actions:
            severity = DriftSeverity.CRITICAL

        alert = DriftAlert(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            identity_id=identity.id,
            identity_display_name=identity.display_name,
            drift_type=DriftType.VELOCITY_ANOMALY,
            action=f"{recent_count} actions in last hour",
            severity=severity,
            status=DriftStatus.OPEN,
            velocity_window_minutes=60,
            velocity_count=recent_count,
            baseline_mean=round(hourly_baseline, 4),
            details=(
                f"Identity '{identity.display_name}' performed {recent_count} "
                f"actions in the last hour ({velocity_ratio:.1f}x baseline rate "
                f"of {hourly_baseline:.1f}/hour)."
            ),
            detected_at=now,
        )
        alerts.append(alert)

        return alerts

    async def detect_all(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[DriftAlert]:
        """Run all detection layers and return combined alerts."""
        baselines = await self._repo.list_baselines(identity.id)

        baseline_actions: set[str] = {b.action for b in baselines}

        first_seen = await self.detect_first_seen(
            tenant_id,
            identity,
            baseline_actions,
        )
        frequency = await self.detect_frequency_anomaly(
            tenant_id,
            identity,
            baselines,
        )
        temporal = await self.detect_temporal_anomaly(
            tenant_id,
            identity,
            baselines,
        )
        velocity = await self.detect_velocity_anomaly(
            tenant_id,
            identity,
            baselines,
        )

        return first_seen + frequency + temporal + velocity
