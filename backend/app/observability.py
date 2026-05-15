# backend/app/observability.py
from __future__ import annotations

import logging

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_observability(settings: Settings) -> None:
    """Configure OpenTelemetry tracing and logging with Azure Monitor export."""
    conn_str = settings.applicationinsights_connection_string
    if not conn_str:
        logger.info("No Application Insights connection string — telemetry disabled")
        return

    try:
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorLogExporter,
            AzureMonitorTraceExporter,
        )
        from opentelemetry import trace
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("OpenTelemetry / Azure Monitor packages not installed — telemetry disabled")
        return

    trace_exporter = AzureMonitorTraceExporter(connection_string=conn_str)
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    log_exporter = AzureMonitorLogExporter(connection_string=conn_str)
    log_provider = LoggerProvider()
    log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    handler = LoggingHandler(logger_provider=log_provider)
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
    except ImportError:
        pass

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except ImportError:
        pass

    logger.info("Application Insights telemetry enabled")
