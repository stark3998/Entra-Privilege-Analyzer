# backend/app/main.py
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings, get_settings
from app.observability import setup_observability
from app.routers import (
    actions,
    best_practices,
    dashboard,
    drift,
    exports,
    health,
    identities,
    narratives,
    project_api,
    projects,
    recommendations,
    reports,
    scans,
    settings_router,
    sync,
    tenants,
    webhooks,
)
from app.services.scan_events import ScanEventBroker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — startup and shutdown logic."""
    settings: Settings = get_settings()

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

    if settings.local_mode:
        logger.warning("LOCAL MODE ACTIVE — authentication disabled")
    app.state.scan_tasks: dict[str, asyncio.Task] = {}
    app.state.instance_id = str(uuid.uuid4())

    # Observability
    setup_observability(settings)

    # Cosmos DB
    from app.services.cosmos import init_cosmos_repo

    repo = None
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            repo = await init_cosmos_repo(settings)
            app.state.cosmos_repo = repo
            logger.info("Cosmos DB connection established")
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

    app.state.scan_event_broker = ScanEventBroker(redis_cache=redis_cache, cosmos_repo=repo)

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
    if repo is not None:
        await repo.close()
        logger.info("Cosmos DB connection closed")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Entra Permissions Analyzer",
        version="0.7.0",
        lifespan=lifespan,
    )
    app.state.scan_tasks: dict[str, asyncio.Task] = {}
    app.state.scan_event_broker = None
    app.state.cosmos_repo = None
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
    app.include_router(tenants.router)
    app.include_router(identities.router)
    app.include_router(actions.router)
    app.include_router(sync.router)
    app.include_router(recommendations.router)
    app.include_router(exports.router)
    app.include_router(drift.router)
    app.include_router(best_practices.router)
    app.include_router(dashboard.router)
    app.include_router(narratives.router)
    app.include_router(webhooks.router)
    app.include_router(reports.router)
    app.include_router(settings_router.router)
    app.include_router(projects.router)
    app.include_router(project_api.router)
    app.include_router(scans.router)

    return app


app = create_app()
