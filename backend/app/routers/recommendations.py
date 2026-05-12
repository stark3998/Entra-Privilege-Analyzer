# backend/app/routers/recommendations.py
from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.identity import IdentityType
from app.pipelines.recommendation_pipeline import RecommendationPipeline
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.role_mapper import RoleMapper
from app.services.role_recommender import RoleRecommender

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/recommendations",
    tags=["recommendations"],
)


class SortField(StrEnum):
    REDUCTION_SCORE = "reduction_score"
    IDENTITY_NAME = "identity_display_name"
    IDENTITY_TYPE = "identity_type"


def _build_pipeline(repo: CosmosRepo) -> RecommendationPipeline:
    """Construct the recommendation pipeline with its dependencies."""
    mapper = RoleMapper()
    recommender = RoleRecommender(mapper)
    return RecommendationPipeline(repo, recommender)


@router.get("")
async def list_recommendations(
    tenant_id: str,
    identity_type: IdentityType | None = None,
    sort_by: SortField = SortField.REDUCTION_SCORE,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_role("IAMAdmin", "SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List role recommendations for a tenant, with optional filters and sorting."""
    validate_tenant_access(tenant_id, user, settings)

    offset = (page - 1) * size
    items, total = await repo.list_recommendations(
        tenant_id=tenant_id,
        identity_type=identity_type.value if identity_type else None,
        offset=offset,
        limit=size,
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/{identity_id}")
async def get_recommendation(
    tenant_id: str,
    identity_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin", "SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get a single recommendation by identity ID."""
    validate_tenant_access(tenant_id, user, settings)

    rec = await repo.get_recommendation(tenant_id, identity_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )
    return rec.model_dump(mode="json")


@router.post("/compute", status_code=status.HTTP_202_ACCEPTED)
async def compute_recommendations(
    tenant_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger batch recommendation computation for all identities in the tenant."""
    validate_tenant_access(tenant_id, user, settings)

    logger.info(
        "audit.recommendations.compute tenant=%s user=%s",
        tenant_id,
        user.oid,
    )

    pipeline = _build_pipeline(repo)
    background_tasks.add_task(pipeline.run, tenant_id)
    return {"status": "accepted", "message": "Recommendation computation started"}
