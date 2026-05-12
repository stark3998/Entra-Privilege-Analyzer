# backend/app/main.py
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.observability import setup_observability
from app.routers import actions, exports, health, identities, recommendations, sync, tenants

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

    if settings.local_mode:
        logger.warning("LOCAL MODE ACTIVE — authentication disabled")

    # Observability
    setup_observability(settings)

    # Cosmos DB
    from app.services.cosmos import init_cosmos_repo

    repo = None
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            repo = await init_cosmos_repo(settings)
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

    yield

    # Shutdown
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
        version="0.3.0",
        lifespan=lifespan,
    )

    # CORS
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
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

    return app


app = create_app()
