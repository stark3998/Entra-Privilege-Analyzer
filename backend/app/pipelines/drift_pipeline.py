# backend/app/pipelines/drift_pipeline.py
"""Orchestrates drift detection across all identities in a tenant."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.models.drift import DriftAlert
from app.models.identity import IdentityProfile
from app.observability import get_tracer
from app.services.drift_detector import DriftDetector
from app.services.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

_ALERT_FLUSH_THRESHOLD = 500


class DriftPipeline:
    """Run drift detection for all identities and update risk scores."""

    def __init__(
        self,
        repo: Any,
        detector: DriftDetector,
        scorer: RiskScorer,
    ) -> None:
        self._repo = repo
        self._detector = detector
        self._scorer = scorer

    async def run(self, tenant_id: str) -> dict[str, Any]:
        """For each identity: detect drift, insert alerts, update risk_score.

        Returns a summary with counts and timing.
        """
        with tracer.start_as_current_span("drift_pipeline.run", attributes={"tenant_id": tenant_id}) as span:
            result = await self._run_inner(tenant_id, span)
            return result

    async def _run_inner(self, tenant_id: str, span: Any) -> dict[str, Any]:
        start = time.monotonic()

        # Paginate through all identities
        all_identities = []
        offset = 0
        page_size = 100
        while True:
            items, total = await self._repo.list_identities(
                offset=offset,
                limit=page_size,
            )
            all_identities.extend(items)
            if offset + page_size >= total:
                break
            offset += page_size

        alerts_created = 0
        identities_processed = 0
        errors = 0

        all_alerts: list[DriftAlert] = []
        updated_identities: list[IdentityProfile] = []

        for identity in all_identities:
            try:
                # Run drift detection
                alerts = await self._detector.detect_all(identity)

                # Buffer alerts for batch write
                all_alerts.extend(alerts)

                # Flush alert buffer mid-loop to avoid unbounded memory
                if len(all_alerts) >= _ALERT_FLUSH_THRESHOLD:
                    alerts_created += await self._repo.batch_upsert_drift_alerts(
                        all_alerts,
                    )
                    all_alerts = []

                # Compute updated risk score
                # Load permission gaps from recommendation (if exists)
                rec = await self._repo.get_recommendation(identity.id)
                permission_gaps = rec.permission_gaps if rec else []

                risk_score = self._scorer.compute_risk_score(
                    identity,
                    alerts,
                    permission_gaps,
                )

                # Buffer identity for batch write
                identity.risk_score = risk_score
                identity.updated_at = datetime.now(UTC)
                updated_identities.append(identity)

                identities_processed += 1

            except Exception:
                logger.exception(
                    "Drift detection failed for %s/%s",
                    tenant_id,
                    identity.id,
                )
                errors += 1

        # Flush remaining buffers
        if all_alerts:
            alerts_created += await self._repo.batch_upsert_drift_alerts(all_alerts)
        if updated_identities:
            await self._repo.batch_upsert_identities(updated_identities)

        duration_ms = int((time.monotonic() - start) * 1000)
        span.set_attribute("identities_processed", identities_processed)
        span.set_attribute("alerts_created", alerts_created)
        span.set_attribute("errors", errors)
        span.set_attribute("duration_ms", duration_ms)

        summary: dict[str, Any] = {
            "tenant_id": tenant_id,
            "identities_processed": identities_processed,
            "alerts_created": alerts_created,
            "errors": errors,
            "duration_ms": duration_ms,
        }
        logger.info("Drift pipeline complete: %s", summary)
        return summary
