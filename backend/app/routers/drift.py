# backend/app/routers/drift.py
"""API endpoints for permission drift detection and baseline management."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.drift import DriftAlertUpdate, DriftSeverity, DriftStatus
from app.pipelines.baseline_pipeline import BaselinePipeline
from app.pipelines.drift_pipeline import DriftPipeline
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.drift_detector import DriftDetector
from app.services.risk_scorer import RiskScorer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}",
    tags=["drift"],
)


# ------------------------------------------------------------------
# Drift alert endpoints
# ------------------------------------------------------------------


@router.get("/drift-alerts")
async def list_drift_alerts(
    tenant_id: str,
    severity: DriftSeverity | None = None,
    drift_status: DriftStatus | None = Query(default=None, alias="status"),
    identity_id: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(require_role("SecurityEngineer", "IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List drift alerts for a tenant, with optional filters and pagination."""
    validate_tenant_access(tenant_id, user, settings)

    offset = (page - 1) * size
    items, total = await repo.list_drift_alerts(
        tenant_id=tenant_id,
        severity=severity.value if severity else None,
        drift_status=drift_status.value if drift_status else None,
        identity_id=identity_id,
        offset=offset,
        limit=size,
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/drift-alerts/{alert_id}")
async def get_drift_alert(
    tenant_id: str,
    alert_id: str,
    user: CurrentUser = Depends(require_role("SecurityEngineer", "IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get a single drift alert by ID."""
    validate_tenant_access(tenant_id, user, settings)

    alert = await repo.get_drift_alert(tenant_id, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drift alert not found",
        )
    return alert.model_dump(mode="json")


@router.patch("/drift-alerts/{alert_id}")
async def update_drift_alert(
    tenant_id: str,
    alert_id: str,
    body: DriftAlertUpdate,
    user: CurrentUser = Depends(require_role("SecurityEngineer", "IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Update drift alert status (acknowledge, escalate, resolve)."""
    validate_tenant_access(tenant_id, user, settings)

    alert = await repo.get_drift_alert(tenant_id, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drift alert not found",
        )

    now = datetime.now(UTC)
    alert.status = body.status

    if body.status == DriftStatus.ACKNOWLEDGED:
        alert.acknowledged_by = body.acknowledged_by or user.email
        alert.acknowledged_at = now
    elif body.status == DriftStatus.RESOLVED:
        alert.resolved_at = now

    updated = await repo.upsert_drift_alert(tenant_id, alert)

    logger.info(
        "audit.drift_alert.update tenant=%s alert=%s status=%s user=%s",
        tenant_id,
        alert_id,
        body.status.value,
        user.oid,
    )

    return updated.model_dump(mode="json")


@router.post("/drift-alerts/detect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_drift_detection(
    tenant_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger on-demand drift detection for a tenant."""
    validate_tenant_access(tenant_id, user, settings)

    logger.info(
        "audit.drift.detect tenant=%s user=%s",
        tenant_id,
        user.oid,
    )

    detector = DriftDetector(repo)
    scorer = RiskScorer()
    pipeline = DriftPipeline(repo, detector, scorer)
    background_tasks.add_task(pipeline.run, tenant_id)

    return {"status": "accepted", "message": "Drift detection started"}


# ------------------------------------------------------------------
# Baseline endpoints
# ------------------------------------------------------------------


@router.get("/baselines/{identity_id}")
async def get_baselines(
    tenant_id: str,
    identity_id: str,
    user: CurrentUser = Depends(require_role("SecurityEngineer")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """View baseline statistics for a specific identity."""
    validate_tenant_access(tenant_id, user, settings)

    baselines = await repo.list_baselines(tenant_id, identity_id)
    return {
        "identity_id": identity_id,
        "baselines": [b.model_dump(mode="json") for b in baselines],
        "count": len(baselines),
    }
