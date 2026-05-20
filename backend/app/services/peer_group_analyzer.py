"""A4: Peer group deviation detection — compares identity behavior to role-based peer groups."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.models.drift import DriftAlert, DriftSeverity, DriftStatus, DriftType
from app.models.identity import IdentityProfile

logger = logging.getLogger(__name__)

_MIN_PEER_GROUP_SIZE = 5
_DEVIATION_THRESHOLD = 2.0


class PeerGroupAnalyzer:
    """Groups identities by role and detects outlier behavior within each peer group."""

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    async def analyze(self, tenant_id: str) -> list[DriftAlert]:
        """Load all identities, group by primary role, detect deviations."""
        all_identities: list[IdentityProfile] = []
        offset = 0
        page_size = 200
        while True:
            items, total = await self._repo.list_identities(
                offset=offset, limit=page_size,
            )
            all_identities.extend(items)
            if offset + page_size >= total:
                break
            offset += page_size

        role_groups: dict[str, list[IdentityProfile]] = defaultdict(list)
        for identity in all_identities:
            primary_role = self._get_primary_role(identity)
            if primary_role:
                role_groups[primary_role].append(identity)

        alerts: list[DriftAlert] = []
        for role_name, members in role_groups.items():
            if len(members) < _MIN_PEER_GROUP_SIZE:
                continue
            alerts.extend(self._detect_deviations(tenant_id, role_name, members))

        return alerts

    def _detect_deviations(
        self,
        tenant_id: str,
        role_name: str,
        members: list[IdentityProfile],
    ) -> list[DriftAlert]:
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        action_counts = [identity.action_count for identity in members]
        if not action_counts:
            return alerts

        mean_count = sum(action_counts) / len(action_counts)
        variance = sum((c - mean_count) ** 2 for c in action_counts) / len(action_counts)
        stddev = variance**0.5

        if stddev == 0:
            return alerts

        for identity in members:
            z = (identity.action_count - mean_count) / stddev
            if z < _DEVIATION_THRESHOLD:
                continue

            if z > 4:
                severity = DriftSeverity.CRITICAL
            elif z > 3:
                severity = DriftSeverity.HIGH
            else:
                severity = DriftSeverity.MEDIUM

            alerts.append(
                DriftAlert(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    identity_id=identity.id,
                    identity_display_name=identity.display_name,
                    drift_type=DriftType.PEER_GROUP_ANOMALY,
                    action=f"{identity.action_count} actions (peer avg: {mean_count:.0f})",
                    severity=severity,
                    status=DriftStatus.OPEN,
                    z_score=round(z, 4),
                    baseline_mean=round(mean_count, 4),
                    baseline_stddev=round(stddev, 4),
                    observed_count=identity.action_count,
                    peer_group_role=role_name,
                    details=(
                        f"Identity '{identity.display_name}' performed "
                        f"{identity.action_count} actions — {z:.1f}x standard "
                        f"deviations above the peer group mean of {mean_count:.0f} "
                        f"for '{role_name}' holders ({len(members)} peers)."
                    ),
                    detected_at=now,
                )
            )

        unique_action_types: dict[str, set[str]] = defaultdict(set)
        for identity in members:
            for oa in identity.observed_actions:
                unique_action_types[identity.id].add(oa.action)

        all_action_sets = list(unique_action_types.values())
        if len(all_action_sets) < _MIN_PEER_GROUP_SIZE:
            return alerts

        common_actions: set[str] = set()
        for action_set in all_action_sets:
            common_actions |= action_set
        action_frequency: dict[str, int] = defaultdict(int)
        for action_set in all_action_sets:
            for action in action_set:
                action_frequency[action] += 1

        rare_threshold = len(all_action_sets) * 0.1

        for identity in members:
            identity_actions = unique_action_types.get(identity.id, set())
            rare_actions = [
                a for a in identity_actions
                if action_frequency.get(a, 0) <= rare_threshold
            ]
            if len(rare_actions) >= 3:
                alerts.append(
                    DriftAlert(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        identity_id=identity.id,
                        identity_display_name=identity.display_name,
                        drift_type=DriftType.PEER_GROUP_ANOMALY,
                        action=f"{len(rare_actions)} unique actions not seen in peer group",
                        severity=DriftSeverity.MEDIUM,
                        status=DriftStatus.OPEN,
                        peer_group_role=role_name,
                        details=(
                            f"Identity '{identity.display_name}' performs "
                            f"{len(rare_actions)} action types rarely seen "
                            f"among '{role_name}' peers: "
                            f"{', '.join(sorted(rare_actions)[:5])}."
                        ),
                        detected_at=now,
                    )
                )

        return alerts

    @staticmethod
    def _get_primary_role(identity: IdentityProfile) -> str | None:
        admin_roles = [
            r for r in identity.current_roles
            if "administrator" in r.role_name.lower() or "global" in r.role_name.lower()
        ]
        if admin_roles:
            return admin_roles[0].role_name

        if identity.current_roles:
            return identity.current_roles[0].role_name

        return None
