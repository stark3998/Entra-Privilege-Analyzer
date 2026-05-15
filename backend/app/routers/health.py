# backend/app/routers/health.py
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe — always returns OK if the process is running."""
    return {"status": "ok"}


@router.get("/sse-test")
async def sse_test() -> StreamingResponse:
    """Minimal SSE test endpoint to diagnose streaming through Envoy."""

    async def generate():
        yield b"data: {\"msg\":\"hello\"}\n\n"
        for i in range(10):
            await asyncio.sleep(2)
            yield f"data: {{\"msg\":\"tick {i}\"}}\n\n".encode()
        yield b"data: {\"msg\":\"done\"}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """Readiness probe — verifies Cosmos DB connectivity."""
    from app.services.cosmos import get_cosmos_repo

    try:
        repo = get_cosmos_repo()
        # Attempt a lightweight read — a missing doc is fine, a connection error is not
        await repo.get_tenant_config("__readyz_probe__")
        return JSONResponse(content={"status": "ready"})
    except RuntimeError:
        # Repo not initialised yet
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "detail": "Cosmos repo not initialised"},
        )
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "detail": str(exc)},
        )
