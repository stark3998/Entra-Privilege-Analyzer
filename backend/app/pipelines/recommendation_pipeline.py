# backend/app/pipelines/recommendation_pipeline.py
"""Orchestrates batch and single-identity recommendation computation."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.models.role import RoleRecommendation
from app.services.cosmos import CosmosRepo
from app.services.role_recommender import RoleRecommender

logger = logging.getLogger(__name__)


class RecommendationPipeline:
    """Compute and persist role recommendations for tenant identities."""

    def __init__(self, repo: CosmosRepo, recommender: RoleRecommender) -> None:
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
                tenant_id=tenant_id, offset=offset, limit=page_size,
            )
            all_identities.extend(items)
            if offset + page_size >= total:
                break
            offset += page_size

        computed = 0
        errors = 0
        for profile in all_identities:
            try:
                rec = self._recommender.compute_recommendation(profile)
                await self._repo.upsert_recommendation(tenant_id, rec)
                computed += 1
            except Exception:
                logger.exception(
                    "Failed to compute recommendation for %s/%s",
                    tenant_id,
                    profile.id,
                )
                errors += 1

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

    async def compute_single(
        self, tenant_id: str, identity_id: str,
    ) -> RoleRecommendation:
        """Compute a recommendation for a single identity and upsert it.

        Raises ``ValueError`` when the identity does not exist.
        """
        profile = await self._repo.get_identity(tenant_id, identity_id)
        if profile is None:
            raise ValueError(f"Identity {identity_id} not found in tenant {tenant_id}")

        rec = self._recommender.compute_recommendation(profile)
        await self._repo.upsert_recommendation(tenant_id, rec)
        return rec
