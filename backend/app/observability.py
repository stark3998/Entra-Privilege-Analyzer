# backend/app/observability.py
from __future__ import annotations

import logging

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_observability(settings: Settings) -> None:
    """Configure OpenTelemetry and Application Insights.

    Currently a stub — full implementation will follow when the
    App Insights resource is provisioned.
    """
    if settings.applicationinsights_connection_string:
        logger.info("Application Insights connection string detected — telemetry will be enabled")
    else:
        logger.info("No Application Insights connection string — telemetry disabled")
