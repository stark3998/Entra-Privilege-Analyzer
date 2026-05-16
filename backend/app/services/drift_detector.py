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

    async def detect_all(
        self,
        tenant_id: str,
        identity: IdentityProfile,
    ) -> list[DriftAlert]:
        """Run both detection layers and return combined alerts."""
        # Load baselines for this identity
        baselines = await self._repo.list_baselines(identity.id)

        # Build baseline action set for first-seen detection
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

        return first_seen + frequency
