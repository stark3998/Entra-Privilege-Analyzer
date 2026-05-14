from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import Settings
from app.pipelines.pim_session_pipeline import PimSessionPipeline
from app.services.cosmos import CosmosRepo
from app.services.crypto import CryptoService
from app.services.graph_ingest import GraphIngestService
from app.services.azure_rm_pim import AzureRmPimService

logger = logging.getLogger(__name__)


class PimSessionPoller:
    """Background task that polls for new PIM activations at a configurable interval."""

    def __init__(self, settings: Settings, repo: CosmosRepo) -> None:
        self._settings = settings
        self._repo = repo

    async def poll_once(self, project_id: str) -> dict[str, Any]:
        project = await self._repo.get_project_by_id(project_id)
        if project is None:
            logger.warning("Poller: project %s not found", project_id)
            return {"error": "project_not_found"}

        crypto = CryptoService(self._settings)
        secret = (
            crypto.decrypt(project.encrypted_client_secret)
            if project.encrypted_client_secret
            else ""
        )
        graph = GraphIngestService(
            self._settings,
            client_id=project.client_id or None,
            client_secret=secret or None,
        )

        arm_pim: AzureRmPimService | None = None
        if project.azure_subscription_ids:
            arm_pim = AzureRmPimService(
                self._settings,
                client_id=project.client_id or None,
                client_secret=secret or None,
            )

        pipeline = PimSessionPipeline(
            self._repo,
            graph,
            arm_pim=arm_pim,
            business_hours_start=self._settings.pim_session_business_hours_start,
            business_hours_end=self._settings.pim_session_business_hours_end,
        )

        return await pipeline.run(
            project.target_tenant_id,
            subscription_ids=project.azure_subscription_ids or None,
            backfill_days=self._settings.pim_session_backfill_days,
        )

    async def start_polling_loop(self, project_id: str) -> None:
        interval = self._settings.pim_session_poll_interval_minutes * 60
        logger.info(
            "Starting PIM session poller for project %s (interval=%ds)",
            project_id, interval,
        )
        while True:
            try:
                summary = await self.poll_once(project_id)
                logger.info("PIM poll cycle for %s: %s", project_id, summary)
            except asyncio.CancelledError:
                logger.info("PIM poller cancelled for project %s", project_id)
                break
            except Exception:
                logger.exception("PIM poll cycle failed for project %s", project_id)
            await asyncio.sleep(interval)
