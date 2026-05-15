# jobs/sync_tenant.py
"""Container Apps Job: sync a tenant's data from Graph API."""

from __future__ import annotations

import asyncio
import logging
import sys

from app.config import get_settings
from app.pipelines.ingest_pipeline import IngestPipeline
from app.services.cosmos import CosmosRepo
from app.services.graph_ingest import GraphIngestService
from app.services.graph_roles import GraphRolesService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the ingest pipeline for all active tenants."""
    settings = get_settings()
    repo = await CosmosRepo.create(settings)

    try:
        graph = GraphIngestService(settings)
        roles = GraphRolesService(graph)
        pipeline = IngestPipeline(repo, graph, roles)

        # Query all tenant configs to find active tenants
        query = "SELECT * FROM c"
        tenant_items: list[dict[str, str]] = [
            item
            async for item in repo._tenant_configs.query_items(
                query=query,
                enable_cross_partition_query=True,
            )
        ]

        if not tenant_items:
            logger.warning("No tenants found — nothing to sync")
            return

        for tenant_doc in tenant_items:
            tenant_id = tenant_doc.get("tenantId", tenant_doc.get("tenant_id", ""))
            if not tenant_id:
                continue
            logger.info("Starting sync for tenant %s", tenant_id)
            try:
                summary = await pipeline.run(tenant_id)
                logger.info("Sync complete for tenant %s: %s", tenant_id, summary)
            except Exception:
                logger.exception("Sync failed for tenant %s", tenant_id)
    finally:
        await repo.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
