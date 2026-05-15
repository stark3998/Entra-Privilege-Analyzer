# backend/app/routers/best_practices.py
"""API endpoints for best practice violation analysis and compliance scoring."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.best_practice import ViolationPriority, ViolationType
from app.services.best_practice_analyzer import BestPracticeAnalyzer
from app.services.cosmos import CosmosRepo, get_cosmos_repo

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/best-practices",
    tags=["best-practices"],
)


@router.get("")
async def list_violations(
    tenant_id: str,
    violation_type: ViolationType | None = Query(default=None, alias="type"),
    priority: ViolationPriority | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_role("IAMAdmin", "SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List best practice violations for a tenant, with optional filters."""
    validate_tenant_access(tenant_id, user, settings)

    offset = (page - 1) * size
    items, total = await repo.list_violations(
        tenant_id=tenant_id,
        violation_type=violation_type.value if violation_type else None,
        priority=priority.value if priority else None,
        offset=offset,
        limit=size,
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/summary")
async def get_compliance_summary(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin", "SecurityEngineer", "Executive")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get aggregated compliance summary for a tenant.

    Runs a live evaluation across all identities and returns the summary.
    """
    validate_tenant_access(tenant_id, user, settings)

    analyzer = BestPracticeAnalyzer(repo)
    _violations, summary = await analyzer.evaluate_tenant(tenant_id)
    return summary.model_dump(mode="json")


@router.get("/{violation_id}")
async def get_violation(
    tenant_id: str,
    violation_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin", "SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get a single violation by ID."""
    validate_tenant_access(tenant_id, user, settings)

    violation = await repo.get_violation(tenant_id, violation_id)
    if violation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found",
        )
    return violation.model_dump(mode="json")


@router.post("/evaluate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation(
    tenant_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger best practice evaluation for all identities in the tenant."""
    validate_tenant_access(tenant_id, user, settings)

    logger.info(
        "audit.best_practices.evaluate tenant=%s user=%s",
        tenant_id,
        user.oid,
    )

    async def _run_evaluation(t_id: str, r: CosmosRepo) -> None:
        analyzer = BestPracticeAnalyzer(r)
        violations, _summary = await analyzer.evaluate_tenant(t_id)
        for v in violations:
            await r.upsert_violation(t_id, v)
        logger.info(
            "Best practice evaluation complete for tenant %s: %d violations",
            t_id,
            len(violations),
        )

    background_tasks.add_task(_run_evaluation, tenant_id, repo)
    return {"status": "accepted", "message": "Best practice evaluation started"}
