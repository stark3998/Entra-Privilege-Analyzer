# backend/app/routers/dashboard.py
"""API endpoints for the executive dashboard."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.narrative import DashboardSummary, DashboardTrends, TrendPoint
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.redis_cache import RedisCache, get_redis_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/dashboard",
    tags=["dashboard"],
)

_DASHBOARD_CACHE_TTL = 300  # 5 minutes


@router.get("")
async def get_dashboard(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("Executive", "IAMAdmin", "SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
    cache: RedisCache | None = Depends(get_redis_cache),
) -> dict[str, Any]:
    """Return the executive dashboard summary for a tenant.

    Caches in Redis for 5 minutes when available.
    """
    validate_tenant_access(tenant_id, user, settings)

    # Try Redis cache first
    cache_key = f"dashboard:{tenant_id}"
    if cache is not None:
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Redis cache read failed: %s", exc)

    summary_data = await repo.get_dashboard_summary(tenant_id)
    summary = DashboardSummary(
        tenant_id=tenant_id,
        total_identities=summary_data.get("total_identities", 0),
        total_actions=summary_data.get("total_actions", 0),
        identities_by_type=summary_data.get("identities_by_type", {}),
        avg_risk_score=summary_data.get("avg_risk_score", 0.0),
        high_risk_count=summary_data.get("high_risk_count", 0),
        drift_alerts_open=summary_data.get("drift_alerts_open", 0),
        drift_alerts_by_severity=summary_data.get("drift_alerts_by_severity", {}),
        compliance_score=summary_data.get("compliance_score", 0.0),
        top_risky_identities=summary_data.get("top_risky_identities", []),
        recommendations_count=summary_data.get("recommendations_count", 0),
        avg_reduction_score=summary_data.get("avg_reduction_score", 0.0),
        computed_at=datetime.now(UTC),
    )
    result = summary.model_dump(mode="json")

    # Cache the result
    if cache is not None:
        try:
            await cache.set(cache_key, json.dumps(result), ttl_seconds=_DASHBOARD_CACHE_TTL)
        except Exception as exc:
            logger.warning("Redis cache write failed: %s", exc)

    return result


@router.get("/trends")
async def get_dashboard_trends(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("Executive", "IAMAdmin", "SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return 30-day trend data for the executive dashboard."""
    validate_tenant_access(tenant_id, user, settings)

    trends_data = await repo.get_trends(tenant_id, days=30)

    trends = DashboardTrends(
        risk_score_trend=[
            TrendPoint(date=d["date"], value=d["value"])
            for d in trends_data.get("risk_score_trend", [])
        ],
        drift_alerts_trend=[
            TrendPoint(date=d["date"], value=d["value"])
            for d in trends_data.get("drift_alerts_trend", [])
        ],
        actions_trend=[
            TrendPoint(date=d["date"], value=d["value"])
            for d in trends_data.get("actions_trend", [])
        ],
    )
    return trends.model_dump(mode="json")
