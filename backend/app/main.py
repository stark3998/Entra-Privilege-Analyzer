# backend/app/main.py
from __future__ import annotations

import asyncio
import logging
import re
import traceback
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings, get_settings
from app.observability import (
    JsonFormatter,
    RequestIdFilter,
    request_id_var,
    setup_observability,
)
from app.routers import (
    health,
    project_api,
    projects,
    scans,
)
from app.services.scan_events import ScanEventBroker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown logic."""
    settings: Settings = get_settings()

    # Logging
    log_level = logging.DEBUG if settings.debug_mode else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        root_logger.addHandler(handler)
    for h in root_logger.handlers:
        if settings.log_format == "json":
            h.setFormatter(JsonFormatter())
        else:
            h.addFilter(RequestIdFilter())
            h.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] — %(message)s")
            )
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    if settings.debug_mode:
        logger.info("DEBUG MODE ACTIVE — verbose errors enabled in HTTP responses")

    if settings.local_mode:
        logger.warning("LOCAL MODE ACTIVE — authentication disabled")
    app.state.scan_tasks: dict[str, asyncio.Task] = {}
    app.state.instance_id = str(uuid.uuid4())

    # Observability
    setup_observability(settings, instance_id=app.state.instance_id)

    # Cosmos DB — master repo + project repo cache
    from azure.cosmos.aio import CosmosClient

    from app.services.master_repo import init_master_repo
    from app.services.project_repo_cache import ProjectRepoCache

    master_repo = None
    project_repo_cache = None
    cosmos_client = None
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            cosmos_client = CosmosClient(
                url=settings.cosmos_endpoint, credential=settings.cosmos_key,
            )
            master_repo = await init_master_repo(settings)
            project_repo_cache = ProjectRepoCache(cosmos_client)
            app.state.cosmos_client = cosmos_client
            app.state.master_repo = master_repo
            app.state.project_repo_cache = project_repo_cache
            logger.info("Cosmos DB initialised — master repo + project repo cache ready")
        except Exception as exc:
            logger.error("Failed to initialise Cosmos DB: %s", exc)
            logger.warning("App starting WITHOUT Cosmos DB — /readyz will report not_ready")
    else:
        logger.warning("Cosmos DB not configured — skipping initialisation")

    # Redis (optional)
    from app.services.redis_cache import init_redis_cache

    redis_cache = None
    try:
        redis_cache = await init_redis_cache(settings)
    except Exception as exc:
        logger.warning("Redis initialisation failed: %s", exc)

    if redis_cache is None and not settings.local_mode:
        raise RuntimeError("Redis is required for distributed scan event streaming")
    if redis_cache is None:
        logger.warning("Redis unavailable — scan events limited to local in-memory streaming")

    app.state.scan_event_broker = ScanEventBroker(
        redis_cache=redis_cache, cosmos_repo=master_repo,
    )

    # Foundry AI (optional)
    from app.services.foundry import init_foundry_client

    foundry = init_foundry_client(settings)
    if foundry is not None:
        logger.info("Foundry AI client initialised")
    else:
        logger.warning("Foundry AI not configured — narratives disabled")

    yield

    # Shutdown
    scan_tasks = list(app.state.scan_tasks.values())
    for task in scan_tasks:
        task.cancel()
    if scan_tasks:
        await asyncio.gather(*scan_tasks, return_exceptions=True)

    broker: ScanEventBroker | None = app.state.scan_event_broker
    if broker is not None:
        await broker.close()

    if redis_cache is not None:
        await redis_cache.close()
        logger.info("Redis connection closed")
    if cosmos_client is not None:
        await cosmos_client.close()
        logger.info("Cosmos client closed")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Entra Permissions Analyzer",
        version="0.8.0",
        lifespan=lifespan,
    )
    app.state.scan_tasks: dict[str, asyncio.Task] = {}
    app.state.scan_event_broker = None
    app.state.master_repo = None
    app.state.project_repo_cache = None
    app.state.cosmos_client = None
    app.state.instance_id = str(uuid.uuid4())

    class SecurityHeadersMiddleware:
        """Pure ASGI middleware — no BaseHTTPMiddleware so StreamingResponse (SSE) is never buffered."""

        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            async def send_with_headers(message: dict) -> None:
                if message["type"] == "http.response.start":
                    extra: list[tuple[bytes, bytes]] = [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    ]
                    if not settings.local_mode:
                        extra.append(
                            (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                        )
                    message = {
                        **message,
                        "headers": list(message.get("headers", [])) + extra,
                    }
                await send(message)

            await self.app(scope, receive, send_with_headers)

    _PROJECT_PATH_RE = re.compile(r"/api/projects/([^/]+)")

    class RequestIdMiddleware:
        """Pure ASGI middleware — injects request ID into context, logs, and spans."""

        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            headers = dict(scope.get("headers", []))
            rid = (headers.get(b"x-request-id", b"") or b"").decode() or str(uuid.uuid4())
            token = request_id_var.set(rid)

            try:
                from opentelemetry import trace

                span = trace.get_current_span()
                if span.is_recording():
                    span.set_attribute("request.id", rid)
                    path = scope.get("path", "")
                    m = _PROJECT_PATH_RE.search(path)
                    if m:
                        span.set_attribute("project.id", m.group(1))
            except Exception:
                pass

            async def send_with_request_id(message: dict) -> None:
                if message["type"] == "http.response.start":
                    message = {
                        **message,
                        "headers": list(message.get("headers", []))
                        + [(b"x-request-id", rid.encode())],
                    }
                await send(message)

            try:
                await self.app(scope, receive, send_with_request_id)
            finally:
                request_id_var.reset(token)

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(project_api.router)
    app.include_router(scans.router)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        from app.exceptions import AppError

        rid = request_id_var.get("")
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = "".join(tb)
        logger.error("Unhandled exception on %s %s:\n%s", request.method, request.url.path, tb_str)

        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span.is_recording():
                span.set_status(trace.StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                span.set_attribute("request.id", rid)
        except Exception:
            pass

        status_code = 500
        error_code = "internal_error"
        if isinstance(exc, AppError):
            status_code = exc.status_code
            error_code = exc.code

        if settings.debug_mode:
            return JSONResponse(
                status_code=status_code,
                content={
                    "detail": str(exc),
                    "code": error_code,
                    "exception_type": type(exc).__qualname__,
                    "traceback": tb_str,
                    "request_id": rid,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
        return JSONResponse(
            status_code=status_code,
            content={"detail": "Internal Server Error", "request_id": rid},
        )

    return app


app = create_app()
