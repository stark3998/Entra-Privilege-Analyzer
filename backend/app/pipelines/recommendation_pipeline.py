# backend/app/pipelines/recommendation_pipeline.py
"""Orchestrates batch and single-identity recommendation computation."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.role import RoleRecommendation
from app.services.role_recommender import RoleRecommender

logger = logging.getLogger(__name__)


class RecommendationPipeline:
    """Compute and persist role recommendations for tenant identities."""

    def __init__(self, repo: Any, recommender: RoleRecommender) -> None:
        self._repo = repo
        self._recommender = recommender

    async def run(self, tenant_id: str) -> dict[str, Any]:
        """Load all identities for the tenant, compute recommendations, upsert to Cosmos.

        Returns a summary dict with counts and timing.
        """
        start = time.monotonic()

        # Fetch all identities (paginate through everything)
        all_identities = []
        page_size = 100
        offset = 0
        while True:
            items, total = await self._repo.list_identities(
                offset=offset,
                limit=page_size,
            )
            all_identities.extend(items)
            if offset + page_size >= total:
                break
            offset += page_size

        computed = 0
        errors = 0
        batch: list[RoleRecommendation] = []
        batch_size = 500

        for profile in all_identities:
            try:
                rec = self._recommender.compute_recommendation(profile)
                batch.append(rec)
            except Exception:
                logger.exception(
                    "Failed to compute recommendation for %s/%s",
                    tenant_id,
                    profile.id,
                )
                errors += 1
                continue

            if len(batch) >= batch_size:
                computed, errors = await self._flush_batch(
                    batch, computed, errors, tenant_id,
                )
                batch = []

        if batch:
            computed, errors = await self._flush_batch(
                batch, computed, errors, tenant_id,
            )

        duration_ms = int((time.monotonic() - start) * 1000)

        summary: dict[str, Any] = {
            "tenant_id": tenant_id,
            "identities_total": len(all_identities),
            "recommendations_computed": computed,
            "errors": errors,
            "duration_ms": duration_ms,
        }
        logger.info("Recommendation pipeline complete: %s", summary)
        return summary

    async def _flush_batch(
        self,
        batch: list[RoleRecommendation],
        computed: int,
        errors: int,
        tenant_id: str,
    ) -> tuple[int, int]:
        """Flush a batch of recommendations via batch upsert.

        Falls back to individual upserts if the batch call fails.
        Returns updated (computed, errors) counters.
        """
        try:
            written = await self._repo.batch_upsert_recommendations(batch)
            computed += written
        except Exception:
            logger.exception(
                "Batch upsert failed for %s (%d items), falling back to individual upserts",
                tenant_id,
                len(batch),
            )
            for rec in batch:
                try:
                    await self._repo.upsert_recommendation(rec)
                    computed += 1
                except Exception:
                    logger.exception(
                        "Failed to upsert recommendation for %s/%s",
                        tenant_id,
                        rec.identity_id if hasattr(rec, "identity_id") else "unknown",
                    )
                    errors += 1
        return computed, errors

    async def compute_single(
        self,
        tenant_id: str,
        identity_id: str,
    ) -> RoleRecommendation:
        """Compute a recommendation for a single identity and upsert it.

        Raises ``ValueError`` when the identity does not exist.
        """
        profile = await self._repo.get_identity(identity_id)
        if profile is None:
            raise ValueError(f"Identity {identity_id} not found in tenant {tenant_id}")

        rec = self._recommender.compute_recommendation(profile)
        await self._repo.upsert_recommendation(rec)
        return rec
