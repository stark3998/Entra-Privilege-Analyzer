# backend/app/services/scheduler.py
"""Scheduled scan execution based on cron configs stored in Cosmos DB.

Runs as a background task inside the FastAPI process. On each tick (60 s)
it queries all enabled ScanSchedule documents, evaluates their cron
expressions, and marks due scans as triggered.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from croniter import croniter

from app.models.alert_rules import ScanSchedule

if TYPE_CHECKING:
    from app.services.cosmos import CosmosRepo

logger = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 60


class ScanScheduler:
    """Manages scheduled scan execution based on cron configs stored in Cosmos."""

    def __init__(self, repo: CosmosRepo) -> None:
        self._repo = repo
        self._running = False
        self._task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ScanScheduler started")

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ScanScheduler stopped")

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Check for due scans every *_CHECK_INTERVAL_SECONDS* seconds."""
        while self._running:
            try:
                await self._check_due_scans()
            except Exception:
                logger.exception("Error in scheduler loop")
            await asyncio.sleep(_CHECK_INTERVAL_SECONDS)

    async def _check_due_scans(self) -> None:
        """Query all enabled schedules and trigger those that are due."""
        schedules = await self._repo.get_scan_schedules()
        now = datetime.now(UTC)

        for schedule in schedules:
            if not schedule.enabled:
                continue
            if schedule.cron_expression is None:
                continue
            if self._is_due(schedule, now):
                logger.info(
                    "Triggering scheduled scan for project %s (types=%s)",
                    schedule.project_id,
                    schedule.job_types,
                )
                await self._trigger_scan(schedule, now)

    # ------------------------------------------------------------------
    # Cron helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_due(schedule: ScanSchedule, now: datetime) -> bool:
        """Return True when *now* is at or past the next cron-derived run time."""
        if schedule.cron_expression is None:
            return False

        if schedule.last_run_at is None:
            return True

        cron = croniter(schedule.cron_expression, schedule.last_run_at)
        next_run: datetime = cron.get_next(datetime)
        # croniter may return a naive datetime — normalise to UTC.
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=UTC)
        return now >= next_run

    async def _trigger_scan(self, schedule: ScanSchedule, now: datetime) -> None:
        """Mark the schedule as run and persist. Actual execution is delegated
        to the ingest pipeline (or an external queue) by the caller that wires
        this scheduler into the app lifecycle.
        """
        schedule.last_run_at = now
        schedule.next_run_at = self.next_run_time(
            schedule.cron_expression or "",
            after=now,
        )
        await self._repo.upsert_scan_schedule(schedule)
        logger.info(
            "Scan triggered: project=%s types=%s next_check=cron(%s)",
            schedule.project_id,
            schedule.job_types,
            schedule.cron_expression,
        )

    # ------------------------------------------------------------------
    # Public utilities
    # ------------------------------------------------------------------

    @staticmethod
    def next_run_time(cron_expression: str, after: datetime | None = None) -> datetime | None:
        """Calculate the next run time for a cron expression.

        Returns None when the expression is empty or invalid.
        """
        if not cron_expression:
            return None
        try:
            base = after or datetime.now(UTC)
            cron = croniter(cron_expression, base)
            next_dt: datetime = cron.get_next(datetime)
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=UTC)
            return next_dt
        except (ValueError, KeyError):
            return None

    @staticmethod
    def validate_cron(cron_expression: str) -> bool:
        """Return True when *cron_expression* is syntactically valid."""
        return croniter.is_valid(cron_expression)
