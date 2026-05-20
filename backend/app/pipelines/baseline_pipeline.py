# backend/app/pipelines/baseline_pipeline.py
"""Computes rolling baseline statistics per identity per action from action events."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.drift import BaselineStats

logger = logging.getLogger(__name__)

_WINDOW_DAYS = 30
_BATCH_SIZE = 500


class BaselinePipeline:
    """Compute rolling baseline statistics for each identity's actions."""

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    async def run(self, tenant_id: str) -> dict[str, Any]:
        """For each identity, compute per-action daily-count statistics over 30 days.

        Groups action events by (identity_id, action, resource), counts per day,
        then computes mean/stddev of daily counts. Upserts BaselineStats documents.
        """
        start = time.monotonic()
        now = datetime.now(UTC)
        window_start = now - timedelta(days=_WINDOW_DAYS)

        # Paginate through all identities
        all_identities_ids: list[tuple[str, str]] = []  # (identity_id, display_name)
        offset = 0
        page_size = 100
        while True:
            items, total = await self._repo.list_identities(
                offset=offset,
                limit=page_size,
            )
            for identity in items:
                all_identities_ids.append((identity.id, identity.display_name))
            if offset + page_size >= total:
                break
            offset += page_size

        baselines_computed = 0
        errors = 0
        pending_baselines: list[BaselineStats] = []

        for identity_id, _ in all_identities_ids:
            try:
                # Fetch action events in the window
                events, _total = await self._repo.list_actions(
                    identity_id=identity_id,
                    start=window_start,
                    end=now,
                    offset=0,
                    limit=10000,  # large limit to get all events in window
                )

                # Group by (action, resource) -> list of dates
                action_dates: dict[tuple[str, str | None], list[str]] = defaultdict(list)
                for event in events:
                    key = (event.action, event.resource)
                    day_str = event.timestamp.strftime("%Y-%m-%d")
                    action_dates[key].append(day_str)

                # Compute daily counts, hour histogram, then mean/stddev
                identity_baselines: list[BaselineStats] = []
                for (action, resource), dates in action_dates.items():
                    daily_counts: dict[str, int] = defaultdict(int)
                    for d in dates:
                        daily_counts[d] += 1

                    counts = list(daily_counts.values())
                    sample_count = len(counts)

                    if sample_count == 0:
                        continue

                    mean = sum(counts) / sample_count
                    variance = sum((c - mean) ** 2 for c in counts) / max(sample_count, 1)
                    stddev = variance**0.5

                    # Build hour-of-day histogram from event timestamps
                    hour_histogram = [0] * 24
                    action_events = [
                        e for e in events
                        if e.action == action and e.resource == resource
                    ]
                    for evt in action_events:
                        hour_histogram[evt.timestamp.hour] += 1

                    # Compute hourly rate baseline
                    total_events = sum(hour_histogram)
                    window_hours = max((_WINDOW_DAYS * 24), 1)
                    actions_per_hour_mean = total_events / window_hours
                    hourly_counts_by_day: dict[str, int] = defaultdict(int)
                    for evt in action_events:
                        key = evt.timestamp.strftime("%Y-%m-%d-%H")
                        hourly_counts_by_day[key] += 1
                    if hourly_counts_by_day:
                        hourly_vals = list(hourly_counts_by_day.values())
                        h_mean = sum(hourly_vals) / len(hourly_vals)
                        h_var = sum((v - h_mean) ** 2 for v in hourly_vals) / len(hourly_vals)
                        actions_per_hour_stddev = h_var**0.5
                    else:
                        actions_per_hour_stddev = 0.0

                    # Deterministic id for the baseline document
                    hash_input = f"{identity_id}|{action}|{resource or ''}"
                    action_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]

                    baseline = BaselineStats(
                        id=f"{identity_id}_{action_hash}",
                        identity_id=identity_id,
                        tenant_id=tenant_id,
                        action=action,
                        resource=resource,
                        mean=round(mean, 4),
                        stddev=round(stddev, 4),
                        sample_count=sample_count,
                        window_start=window_start,
                        window_end=now,
                        updated_at=now,
                        hour_histogram=hour_histogram,
                        actions_per_hour_mean=round(actions_per_hour_mean, 4),
                        actions_per_hour_stddev=round(actions_per_hour_stddev, 4),
                    )

                    identity_baselines.append(baseline)

                pending_baselines.extend(identity_baselines)

                # Flush when buffer reaches batch size
                if len(pending_baselines) >= _BATCH_SIZE:
                    baselines_computed += await self._flush_baselines(pending_baselines, tenant_id)
                    pending_baselines = []

            except Exception:
                logger.exception(
                    "Failed to compute baselines for %s/%s",
                    tenant_id,
                    identity_id,
                )
                errors += 1

        # Flush any remaining baselines after the loop
        if pending_baselines:
            baselines_computed += await self._flush_baselines(pending_baselines, tenant_id)

        duration_ms = int((time.monotonic() - start) * 1000)

        summary: dict[str, Any] = {
            "tenant_id": tenant_id,
            "identities_processed": len(all_identities_ids),
            "baselines_computed": baselines_computed,
            "errors": errors,
            "duration_ms": duration_ms,
        }
        logger.info("Baseline pipeline complete: %s", summary)
        return summary

    async def _flush_baselines(self, baselines: list[BaselineStats], tenant_id: str) -> int:
        """Flush a batch of baselines via batch_upsert, falling back to individual upserts."""
        try:
            return await self._repo.batch_upsert_baselines(baselines)
        except Exception:
            logger.warning(
                "Batch upsert failed for %d baselines in tenant %s, falling back to individual upserts",
                len(baselines),
                tenant_id,
                exc_info=True,
            )
            count = 0
            for baseline in baselines:
                try:
                    await self._repo.upsert_baseline(baseline)
                    count += 1
                except Exception:
                    logger.exception(
                        "Individual upsert fallback failed for baseline %s",
                        baseline.id,
                    )
            return count
