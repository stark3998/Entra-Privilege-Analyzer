from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from app.models.tenant_evidence import ActionFeatureAggregate, ActivityEvidence


class EvidenceAggregator:
    """Builds replay-safe hourly, daily, and weekly activity feature buckets."""

    def aggregate(
        self,
        events: Iterable[ActivityEvidence],
    ) -> list[ActionFeatureAggregate]:
        aggregates: dict[
            tuple[str, str, str, datetime],
            ActionFeatureAggregate,
        ] = {}
        resources: dict[tuple[str, str, str, datetime], set[str]] = {}
        for event in events:
            for bucket in ("hour", "day", "week"):
                start = _bucket_start(event.occurred_at, bucket)
                key = (event.principal_id, event.action, bucket, start)
                current = aggregates.get(key)
                if current is None:
                    current = ActionFeatureAggregate(
                        id=_feature_id(event.tenant_id, *key),
                        tenant_id=event.tenant_id,
                        principal_id=event.principal_id,
                        action=event.action,
                        bucket=bucket,
                        bucket_start=start,
                        first_seen=event.occurred_at,
                        last_seen=event.occurred_at,
                    )
                resource_set = resources.setdefault(key, set())
                if event.resource_id:
                    resource_set.add(event.resource_id)
                aggregates[key] = current.model_copy(
                    update={
                        "count": current.count + 1,
                        "success_count": current.success_count
                        + (1 if event.result == "success" else 0),
                        "failure_count": current.failure_count
                        + (1 if event.result != "success" else 0),
                        "distinct_resource_count": len(resource_set),
                        "first_seen": min(current.first_seen, event.occurred_at),
                        "last_seen": max(current.last_seen, event.occurred_at),
                    }
                )
        return list(aggregates.values())


def _bucket_start(value: datetime, bucket: str) -> datetime:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    if bucket == "hour":
        return aware.replace(minute=0, second=0, microsecond=0)
    day = aware.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "day":
        return day
    return day - timedelta(days=day.weekday())


def _feature_id(
    tenant_id: str,
    principal_id: str,
    action: str,
    bucket: str,
    bucket_start: datetime,
) -> str:
    raw = f"{tenant_id}:{principal_id}:{action}:{bucket}:{bucket_start.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()
