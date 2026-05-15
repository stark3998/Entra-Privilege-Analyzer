# backend/app/pipelines/drift_pipeline.py
"""Orchestrates drift detection across all identities in a tenant."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.services.cosmos import CosmosRepo
from app.services.drift_detector import DriftDetector
from app.services.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)


class DriftPipeline:
    """Run drift detection for all identities and update risk scores."""

    def __init__(
        self,
        repo: CosmosRepo,
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
        start = time.monotonic()

        # Paginate through all identities
        all_identities = []
        offset = 0
        page_size = 100
        while True:
            items, total = await self._repo.list_identities(
                tenant_id=tenant_id,
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

        for identity in all_identities:
            try:
                # Run drift detection
                alerts = await self._detector.detect_all(tenant_id, identity)

                # Persist new alerts
                for alert in alerts:
                    await self._repo.upsert_drift_alert(tenant_id, alert)
                    alerts_created += 1

                # Compute updated risk score
                # Load permission gaps from recommendation (if exists)
                rec = await self._repo.get_recommendation(tenant_id, identity.id)
                permission_gaps = rec.permission_gaps if rec else []

                risk_score = self._scorer.compute_risk_score(
                    identity,
                    alerts,
                    permission_gaps,
                )

                # Update identity risk_score
                identity.risk_score = risk_score
                identity.updated_at = datetime.now(UTC)
                await self._repo.upsert_identity(tenant_id, identity)

                identities_processed += 1

            except Exception:
                logger.exception(
                    "Drift detection failed for %s/%s",
                    tenant_id,
                    identity.id,
                )
                errors += 1

        duration_ms = int((time.monotonic() - start) * 1000)

        summary: dict[str, Any] = {
            "tenant_id": tenant_id,
            "identities_processed": identities_processed,
            "alerts_created": alerts_created,
            "errors": errors,
            "duration_ms": duration_ms,
        }
        logger.info("Drift pipeline complete: %s", summary)
        return summary
