from __future__ import annotations

import contextvars
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


class RequestIdFilter(logging.Filter):
    """Inject request_id into every LogRecord for text-mode formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")  # type: ignore[attr-defined]
        return True


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter with OTel trace context."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = ""
        span_id = ""
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context()
            if ctx and ctx.trace_id:
                trace_id = format(ctx.trace_id, "032x")
                span_id = format(ctx.span_id, "016x")
        except Exception:
            pass

        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(""),
            "trace_id": trace_id,
            "span_id": span_id,
        }
        if record.exc_info and record.exc_info[1] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


# ---------------------------------------------------------------------------
# Tracer / meter accessors (no-op safe when OTel is not configured)
# ---------------------------------------------------------------------------


def get_tracer(name: str = __name__) -> Any:
    from opentelemetry import trace

    return trace.get_tracer(name)


def get_meter(name: str = __name__) -> Any:
    from opentelemetry import metrics

    return metrics.get_meter(name)


# ---------------------------------------------------------------------------
# Custom metrics (created lazily on first call)
# ---------------------------------------------------------------------------

_metrics_initialized = False
scan_duration_histogram: Any = None
scan_events_counter: Any = None
scan_identities_counter: Any = None
cosmos_ru_counter: Any = None
graph_api_request_counter: Any = None


def _init_custom_metrics() -> None:
    global _metrics_initialized, scan_duration_histogram, scan_events_counter
    global scan_identities_counter, cosmos_ru_counter, graph_api_request_counter

    if _metrics_initialized:
        return
    _metrics_initialized = True

    meter = get_meter("entra-permissions-analyzer")
    scan_duration_histogram = meter.create_histogram(
        "scan.duration", unit="ms", description="Scan pipeline duration"
    )
    scan_events_counter = meter.create_counter(
        "scan.events_ingested", description="Total action events ingested"
    )
    scan_identities_counter = meter.create_counter(
        "scan.identities_processed", description="Total identities processed"
    )
    cosmos_ru_counter = meter.create_counter(
        "cosmos.request_units", unit="RU", description="Cosmos DB request units consumed"
    )
    graph_api_request_counter = meter.create_counter(
        "graph_api.requests", description="Microsoft Graph API requests"
    )


# ---------------------------------------------------------------------------
# Setup entry point
# ---------------------------------------------------------------------------


def setup_observability(settings: Settings, *, instance_id: str = "") -> None:
    """Configure OpenTelemetry tracing, metrics, and logging with Azure Monitor export."""
    conn_str = settings.applicationinsights_connection_string
    if not conn_str:
        logger.info("No Application Insights connection string — telemetry disabled")
        _init_custom_metrics()
        return

    try:
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorLogExporter,
            AzureMonitorMetricExporter,
            AzureMonitorTraceExporter,
        )
        from opentelemetry import metrics, trace
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("OpenTelemetry / Azure Monitor packages not installed — telemetry disabled")
        _init_custom_metrics()
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.8.0",
            "service.instance.id": instance_id or "unknown",
        }
    )

    # Traces
    trace_exporter = AzureMonitorTraceExporter(connection_string=conn_str)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_exporter = AzureMonitorMetricExporter(connection_string=conn_str)
    metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Logs
    log_exporter = AzureMonitorLogExporter(connection_string=conn_str)
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    handler = LoggingHandler(logger_provider=log_provider)
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)

    # Auto-instrumentation
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

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except ImportError:
        pass

    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=False)
    except ImportError:
        pass

    _init_custom_metrics()
    logger.info("Application Insights telemetry enabled (traces + metrics + logs)")
