# jobs/generate_narratives.py
"""Container Apps Job: generate AI narratives for all active tenants."""
from __future__ import annotations

import asyncio
import logging
import sys

from app.config import get_settings
from app.services.cosmos import CosmosRepo
from app.services.foundry import FoundryClient, init_foundry_client
from app.services.narrative_engine import NarrativeEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Generate executive narratives for all active tenants."""
    settings = get_settings()
    repo = await CosmosRepo.create(settings)

    foundry = init_foundry_client(settings)
    if foundry is None:
        logger.error("Foundry not configured — cannot generate narratives")
        return

    try:
        engine = NarrativeEngine(client=foundry, repo=repo)

        # Query all tenant configs
        query = "SELECT * FROM c"
        tenant_items: list[dict[str, str]] = [
            item
            async for item in repo._tenant_configs.query_items(
                query=query,
                enable_cross_partition_query=True,
            )
        ]

        if not tenant_items:
            logger.warning("No tenants found — nothing to generate")
            return

        for tenant_doc in tenant_items:
            tenant_id = tenant_doc.get("tenantId", tenant_doc.get("tenant_id", ""))
            if not tenant_id:
                continue
            logger.info("Generating narratives for tenant %s", tenant_id)
            try:
                narrative = await engine.generate_executive_digest(tenant_id)
                logger.info(
                    "Narrative generated for tenant %s: scope=%s",
                    tenant_id,
                    narrative.scope,
                )
            except Exception:
                logger.exception(
                    "Narrative generation failed for tenant %s", tenant_id,
                )
    finally:
        await repo.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
