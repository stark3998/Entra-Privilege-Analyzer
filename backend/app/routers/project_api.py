"""Project-scoped wrappers for all tenant-scoped endpoints.

Each endpoint validates project access, extracts the target_tenant_id,
and delegates to the ProjectRepo (per-project database) for analysis data
and MasterRepo for project-level metadata (schedules, alerts).
"""

from __future__ import annotations

import io
import json
import logging
import re
import uuid
import zipfile
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse

from app.auth.deps import CurrentUser, get_current_user, validate_project_access
from app.config import Settings, get_settings
from app.models.best_practice import ViolationPriority, ViolationType
from app.models.drift import DriftAlertUpdate, DriftSeverity, DriftStatus
from app.models.export import ExportFormat
from app.models.identity import IdentityType
from app.models.narrative import (
    AnalyticsData,
    DashboardSummary,
    DashboardTrends,
    NarrativeScope,
    TrendPoint,
)
from app.pipelines.drift_pipeline import DriftPipeline
from app.pipelines.recommendation_pipeline import RecommendationPipeline
from app.services.best_practice_analyzer import BestPracticeAnalyzer
from app.services.drift_detector import DriftDetector
from app.services.foundry import FoundryClient, get_foundry_client
from app.services.iac_exporter import IacExporter
from app.services.master_repo import MasterRepo, get_master_repo
from app.services.narrative_engine import NarrativeEngine
from app.services.project_repo import ProjectRepo
from app.services.project_repo_cache import ProjectRepoCache
from app.services.redis_cache import RedisCache, get_redis_cache
from app.services.report_generator import ReportGenerator
from app.services.risk_scorer import RiskScorer
from app.services.role_mapper import RoleMapper
from app.services.role_recommender import RoleRecommender

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["project-api"])

_DASHBOARD_CACHE_TTL = 300
_exporter = IacExporter()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


async def _get_project_context(
    project_id: str,
    user: CurrentUser,
    repo: MasterRepo,
    request: Request,
    settings: Settings,
    required_role: str | None = None,
) -> tuple[str, ProjectRepo]:
    """Validate access and return (target_tenant_id, ProjectRepo)."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role=required_role,
    )
    cache: ProjectRepoCache = request.app.state.project_repo_cache
    project_repo = await cache.get_repo(project.database_name)
    return project.target_tenant_id, project_repo


# ------------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------------


@router.get("/dashboard")
async def get_dashboard(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
    cache: RedisCache | None = Depends(get_redis_cache),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)

    cache_key = f"dashboard:{project_id}"
    if cache is not None:
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    data = await project_repo.get_dashboard_summary()
    summary = DashboardSummary(
        tenant_id=tid,
        total_identities=data.get("total_identities", 0),
        total_actions=data.get("total_actions", 0),
        identities_by_type=data.get("identities_by_type", {}),
        avg_risk_score=data.get("avg_risk_score", 0.0),
        high_risk_count=data.get("high_risk_count", 0),
        drift_alerts_open=data.get("drift_alerts_open", 0),
        drift_alerts_by_severity=data.get("drift_alerts_by_severity", {}),
        compliance_score=data.get("compliance_score", 0.0),
        top_risky_identities=data.get("top_risky_identities", []),
        recommendations_count=data.get("recommendations_count", 0),
        avg_reduction_score=data.get("avg_reduction_score", 0.0),
        computed_at=datetime.now(UTC),
    )
    result = summary.model_dump(mode="json")

    if cache is not None:
        try:
            await cache.set(cache_key, json.dumps(result), ttl_seconds=_DASHBOARD_CACHE_TTL)
        except Exception:
            pass

    return result


@router.get("/dashboard/trends")
async def get_dashboard_trends(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    trends_data = await project_repo.get_trends(days=30)
    trends = DashboardTrends(
        risk_score_trend=[TrendPoint(**d) for d in trends_data.get("risk_score_trend", [])],
        drift_alerts_trend=[TrendPoint(**d) for d in trends_data.get("drift_alerts_trend", [])],
        actions_trend=[TrendPoint(**d) for d in trends_data.get("actions_trend", [])],
    )
    return trends.model_dump(mode="json")


# ------------------------------------------------------------------
# Analytics
# ------------------------------------------------------------------


@router.get("/analytics")
async def get_analytics(
    project_id: str,
    request: Request,
    days: int = Query(default=30, ge=7, le=90),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
    cache: RedisCache | None = Depends(get_redis_cache),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)

    cache_key = f"analytics:{project_id}:{days}"
    if cache is not None:
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    data = await project_repo.get_analytics_data(days)
    result = AnalyticsData(
        tenant_id=tid,
        days=days,
        total_actions=data.get("total_actions", 0),
        unique_active_identities=data.get("unique_active_identities", 0),
        avg_actions_per_identity=data.get("avg_actions_per_identity", 0.0),
        failed_action_pct=data.get("failed_action_pct", 0.0),
        new_identities_count=data.get("new_identities_count", 0),
        daily_action_counts=[TrendPoint(**d) for d in data.get("daily_action_counts", [])],
        top_actions=data.get("top_actions", []),
        most_active_identities=data.get("most_active_identities", []),
        actions_by_source=data.get("actions_by_source", {}),
        success_vs_failure=data.get("success_vs_failure", {}),
        top_resources=data.get("top_resources", []),
        top_roles=data.get("top_roles", []),
        permission_utilization=data.get("permission_utilization", {"used": 0, "unused": 0}),
        permanent_vs_pim=data.get("permanent_vs_pim", {"permanent": 0, "pim": 0}),
        overprivileged_count=data.get("overprivileged_count", 0),
        violations_by_type=data.get("violations_by_type", {}),
        stale_identity_counts=data.get("stale_identity_counts", {}),
        credential_expiry_violations=data.get("credential_expiry_violations", []),
        recent_drift_alerts=data.get("recent_drift_alerts", []),
        computed_at=datetime.now(UTC),
    ).model_dump(mode="json")

    if cache is not None:
        try:
            await cache.set(cache_key, json.dumps(result), ttl_seconds=_DASHBOARD_CACHE_TTL)
        except Exception:
            pass

    return result


# ------------------------------------------------------------------
# Identities
# ------------------------------------------------------------------


@router.get("/identities")
async def list_identities(
    project_id: str,
    request: Request,
    type: str | None = None,
    search: str | None = None,
    page: int = 1,
    size: int = 50,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_identities(type, search, offset, size)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/identities/{identity_id}")
async def get_identity(
    project_id: str,
    identity_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    profile = await project_repo.get_identity(identity_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Identity not found")
    return profile.model_dump(mode="json")


@router.get("/identities/{identity_id}/actions")
async def list_actions(
    project_id: str,
    identity_id: str,
    request: Request,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    size: int = 50,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_actions(identity_id, start, end, offset, size)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


# ------------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------------


@router.get("/recommendations")
async def list_recommendations(
    project_id: str,
    request: Request,
    identity_type: IdentityType | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_recommendations(
        identity_type.value if identity_type else None,
        offset,
        size,
    )
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/recommendations/{identity_id}")
async def get_recommendation(
    project_id: str,
    identity_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    rec = await project_repo.get_recommendation(identity_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec.model_dump(mode="json")


@router.post("/recommendations/compute", status_code=status.HTTP_202_ACCEPTED)
async def compute_recommendations(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    mapper = RoleMapper()
    recommender = RoleRecommender(mapper)
    pipeline = RecommendationPipeline(project_repo, recommender)
    background_tasks.add_task(pipeline.run, tid)
    return {"status": "accepted", "message": "Recommendation computation started"}


# ------------------------------------------------------------------
# Exports
# ------------------------------------------------------------------


@router.get("/exports/{identity_id}")
async def export_recommendation(
    project_id: str,
    identity_id: str,
    request: Request,
    format: ExportFormat = Query(default=ExportFormat.TERRAFORM),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    rec = await project_repo.get_recommendation(identity_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    result = _exporter.export(rec, format)
    return result.model_dump(mode="json")


@router.post("/exports/bulk")
async def bulk_export(
    project_id: str,
    request: Request,
    format: ExportFormat = Query(default=ExportFormat.TERRAFORM),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    items, _ = await project_repo.list_recommendations(offset=0, limit=500)
    if not items:
        raise HTTPException(status_code=404, detail="No recommendations found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rec in items:
            result = _exporter.export(rec, format)
            zf.writestr(result.filename, result.content)
    buf.seek(0)
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", project_id)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="roles-{safe}.zip"'},
    )


# ------------------------------------------------------------------
# Drift alerts
# ------------------------------------------------------------------


@router.get("/drift-alerts")
async def list_drift_alerts(
    project_id: str,
    request: Request,
    severity: DriftSeverity | None = None,
    drift_status: DriftStatus | None = Query(default=None, alias="status"),
    identity_id: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_drift_alerts(
        severity.value if severity else None,
        drift_status.value if drift_status else None,
        identity_id,
        offset,
        size,
    )
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/drift-alerts/{alert_id}")
async def get_drift_alert(
    project_id: str,
    alert_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    alert = await project_repo.get_drift_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Drift alert not found")
    return alert.model_dump(mode="json")


@router.patch("/drift-alerts/{alert_id}")
async def update_drift_alert(
    project_id: str,
    alert_id: str,
    body: DriftAlertUpdate,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    alert = await project_repo.get_drift_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Drift alert not found")
    now = datetime.now(UTC)
    alert.status = body.status
    if body.status == DriftStatus.ACKNOWLEDGED:
        alert.acknowledged_by = body.acknowledged_by or user.email
        alert.acknowledged_at = now
    elif body.status == DriftStatus.RESOLVED:
        alert.resolved_at = now
    updated = await project_repo.upsert_drift_alert(alert)
    return updated.model_dump(mode="json")


@router.post("/drift-alerts/detect", status_code=status.HTTP_202_ACCEPTED)
async def trigger_drift_detection(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    detector = DriftDetector(project_repo)
    scorer = RiskScorer()
    pipeline = DriftPipeline(project_repo, detector, scorer)
    background_tasks.add_task(pipeline.run, tid)
    return {"status": "accepted", "message": "Drift detection started"}


@router.get("/baselines/{identity_id}")
async def get_baselines(
    project_id: str,
    identity_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    baselines = await project_repo.list_baselines(identity_id)
    return {
        "identity_id": identity_id,
        "baselines": [b.model_dump(mode="json") for b in baselines],
        "count": len(baselines),
    }


# ------------------------------------------------------------------
# Best practices
# ------------------------------------------------------------------


@router.get("/best-practices")
async def list_violations(
    project_id: str,
    request: Request,
    violation_type: ViolationType | None = Query(default=None, alias="type"),
    priority: ViolationPriority | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_violations(
        violation_type.value if violation_type else None,
        priority.value if priority else None,
        offset,
        size,
    )
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/best-practices/summary")
async def get_compliance_summary(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    analyzer = BestPracticeAnalyzer(project_repo)
    _violations, summary = await analyzer.evaluate_tenant(tid)
    return summary.model_dump(mode="json")


@router.get("/best-practices/{violation_id}")
async def get_violation(
    project_id: str,
    violation_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    violation = await project_repo.get_violation(violation_id)
    if violation is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    return violation.model_dump(mode="json")


@router.post("/best-practices/evaluate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_evaluation(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )

    async def _run(t: str, r: ProjectRepo) -> None:
        analyzer = BestPracticeAnalyzer(r)
        violations, _ = await analyzer.evaluate_tenant(t)
        for v in violations:
            await r.upsert_violation(v)

    background_tasks.add_task(_run, tid, project_repo)
    return {"status": "accepted", "message": "Best practice evaluation started"}


# ------------------------------------------------------------------
# Narratives
# ------------------------------------------------------------------


def _get_engine(repo: ProjectRepo, foundry: FoundryClient | None) -> NarrativeEngine:
    if foundry is None:
        raise HTTPException(status_code=503, detail="AI narrative generation is not configured")
    return NarrativeEngine(client=foundry, repo=repo)


@router.get("/narratives/executive")
async def get_executive_narrative(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    foundry: FoundryClient | None = Depends(get_foundry_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    engine = _get_engine(project_repo, foundry)
    narrative = await engine.get_or_generate(tid, NarrativeScope.EXECUTIVE, "tenant")
    return narrative.model_dump(mode="json")


@router.post("/narratives/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_narratives(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    foundry: FoundryClient | None = Depends(get_foundry_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    engine = _get_engine(project_repo, foundry)
    await engine.generate_executive_digest(tid)
    return {"status": "accepted", "message": "Narrative regeneration started"}


# ------------------------------------------------------------------
# Reports
# ------------------------------------------------------------------


@router.get("/reports/executive")
async def download_executive_report(
    project_id: str,
    request: Request,
    format: str = Query(default="pdf", pattern="^(pdf|pptx)$"),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    generator = ReportGenerator(project_repo)
    if format == "pdf":
        content = await generator.generate_executive_pdf(tid)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{project_id}.pdf"'},
        )
    content = await generator.generate_executive_pptx(tid)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="report_{project_id}.pptx"'},
    )


# ------------------------------------------------------------------
# App Registrations
# ------------------------------------------------------------------


@router.get("/app-registrations")
async def list_app_registrations(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_app_registrations(offset, size)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/app-registrations/{app_id}")
async def get_app_registration(
    project_id: str,
    app_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    app = await project_repo.get_app_registration(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="App registration not found")
    return app.model_dump(mode="json")


# ------------------------------------------------------------------
# Conditional Access
# ------------------------------------------------------------------


@router.get("/conditional-access")
async def list_ca_policies(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    policies = await project_repo.list_ca_policies()
    return {"items": [p.model_dump(mode="json") for p in policies], "total": len(policies)}


@router.post("/conditional-access/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_ca_policies(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    from app.services.ca_analyzer import ConditionalAccessAnalyzer

    async def _run(t: str, r: ProjectRepo) -> None:
        policies = await r.list_ca_policies()
        analyzer = ConditionalAccessAnalyzer()
        violations = analyzer.evaluate_policies(t, policies)
        for v in violations:
            await r.upsert_violation(v)

    background_tasks.add_task(_run, tid, project_repo)
    return {"status": "accepted", "message": "CA policy analysis started"}


# ------------------------------------------------------------------
# Groups
# ------------------------------------------------------------------


@router.get("/groups")
async def list_groups(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_groups(offset, size)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/groups/{group_id}")
async def get_group(
    project_id: str,
    group_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    group = await project_repo.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group.model_dump(mode="json")


# ------------------------------------------------------------------
# Custom Roles
# ------------------------------------------------------------------


@router.get("/custom-roles")
async def list_custom_roles(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    items = await project_repo.list_custom_roles()
    return {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}


# ------------------------------------------------------------------
# Access Reviews
# ------------------------------------------------------------------


@router.get("/access-reviews")
async def list_access_reviews(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    items = await project_repo.list_access_reviews()
    return {"items": [i.model_dump(mode="json") for i in items], "total": len(items)}


# ------------------------------------------------------------------
# SoD Rules
# ------------------------------------------------------------------


@router.get("/settings/sod-rules")
async def list_sod_rules(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    rules = await project_repo.get_sod_rules()
    return {"items": [r.model_dump(mode="json") for r in rules], "total": len(rules)}


@router.post("/settings/sod-rules")
async def create_sod_rule(
    project_id: str,
    body: dict[str, Any],
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    from app.models.sod_policy import SodConflictRule

    rule = SodConflictRule(
        id=str(uuid.uuid4()),
        tenant_id=tid,
        role_a_name=body["role_a_name"],
        role_b_name=body["role_b_name"],
        severity=body.get("severity", "high"),
        rationale=body.get("rationale", ""),
        is_custom=True,
        enabled=True,
    )
    saved = await project_repo.upsert_sod_rule(rule)
    return saved.model_dump(mode="json")


@router.delete("/settings/sod-rules/{rule_id}")
async def delete_sod_rule(
    project_id: str,
    rule_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    await project_repo.delete_sod_rule(rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Remediation
# ------------------------------------------------------------------


@router.get("/remediation")
async def list_remediation_actions(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_remediation_actions(offset, size)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/remediation/request")
async def request_remediation(
    project_id: str,
    body: dict[str, Any],
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    from app.services.remediation_engine import RemediationEngine

    engine = RemediationEngine(project_repo)
    action = await engine.request_action(
        tenant_id=tid,
        project_id=project_id,
        action_type=body["action_type"],
        target_identity_id=body["target_identity_id"],
        target_resource_id=body.get("target_resource_id"),
        justification=body.get("justification", ""),
        requested_by=user.email,
    )
    return action.model_dump(mode="json")


@router.post("/remediation/{action_id}/approve")
async def approve_remediation(
    project_id: str,
    action_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    from app.services.remediation_engine import RemediationEngine

    engine = RemediationEngine(project_repo)
    action = await engine.approve_action(tid, action_id, user.email)
    return action.model_dump(mode="json")


@router.post("/remediation/{action_id}/reject")
async def reject_remediation(
    project_id: str,
    action_id: str,
    request: Request,
    body: dict[str, Any] | None = None,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(
        project_id, user, repo, request, settings, required_role="operator"
    )
    from app.services.remediation_engine import RemediationEngine

    engine = RemediationEngine(project_repo)
    reason = (body or {}).get("reason", "")
    action = await engine.reject_action(tid, action_id, user.email, reason)
    return action.model_dump(mode="json")


# ------------------------------------------------------------------
# Scan Schedules
# ------------------------------------------------------------------


@router.get("/settings/scan-schedules")
async def list_scan_schedules(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    await _get_project_context(project_id, user, repo, request, settings)
    schedules = await repo.get_scan_schedules_for_project(project_id)
    return {"items": [s.model_dump(mode="json") for s in schedules], "total": len(schedules)}


@router.post("/settings/scan-schedules")
async def create_scan_schedule(
    project_id: str,
    body: dict[str, Any],
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    await _get_project_context(project_id, user, repo, request, settings, required_role="operator")
    from app.models.alert_rules import ScanSchedule

    schedule = ScanSchedule(
        id=str(uuid.uuid4()),
        project_id=project_id,
        cron_expression=body.get("cron_expression"),
        job_types=body.get("job_types", ["incremental_sync"]),
        enabled=body.get("enabled", True),
    )
    saved = await repo.upsert_scan_schedule(schedule)
    return saved.model_dump(mode="json")


@router.delete("/settings/scan-schedules/{schedule_id}")
async def delete_scan_schedule(
    project_id: str,
    schedule_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    await _get_project_context(project_id, user, repo, request, settings, required_role="operator")
    await repo.delete_scan_schedule(project_id, schedule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Alert Rules
# ------------------------------------------------------------------


@router.get("/settings/alert-rules")
async def list_alert_rules(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    await _get_project_context(project_id, user, repo, request, settings)
    rules = await repo.get_alert_rules_for_project(project_id)
    return {"items": [r.model_dump(mode="json") for r in rules], "total": len(rules)}


@router.post("/settings/alert-rules")
async def create_alert_rule(
    project_id: str,
    body: dict[str, Any],
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    await _get_project_context(project_id, user, repo, request, settings, required_role="operator")
    from app.models.alert_rules import AlertChannel, AlertChannelType, AlertRule, AlertRuleType

    channel = AlertChannel(
        channel_type=AlertChannelType(body["channel"]["channel_type"]),
        config=body["channel"].get("config", {}),
    )
    rule = AlertRule(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tenant_id=body.get("tenant_id", ""),
        rule_type=AlertRuleType(body.get("rule_type", "event")),
        condition=body.get("condition", {}),
        channel=channel,
        severity_filter=body.get("severity_filter"),
        enabled=body.get("enabled", True),
    )
    saved = await repo.upsert_alert_rule(rule)
    return saved.model_dump(mode="json")


@router.delete("/settings/alert-rules/{rule_id}")
async def delete_alert_rule(
    project_id: str,
    rule_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    await _get_project_context(project_id, user, repo, request, settings, required_role="operator")
    await repo.delete_alert_rule(project_id, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------
# Compliance Reports
# ------------------------------------------------------------------


@router.get("/reports/compliance")
async def get_compliance_report(
    project_id: str,
    request: Request,
    framework: str = Query(pattern="^(soc2|iso27001|nist80053)$"),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    from app.data.compliance_mappings import get_compliance_controls

    violations, _ = await project_repo.list_violations(offset=0, limit=1000)
    controls: list[dict[str, Any]] = []
    for v in violations:
        mapping = get_compliance_controls(v.violation_type, framework)
        if mapping:
            controls.append(
                {
                    "violation_id": v.id,
                    "violation_type": v.violation_type,
                    "severity": v.priority,
                    "resolved": v.resolved,
                    "controls": mapping,
                }
            )
    return {
        "framework": framework,
        "tenant_id": tid,
        "total_mapped_violations": len(controls),
        "controls": controls,
    }


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------


@router.get("/settings")
async def get_project_settings(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    project = await validate_project_access(project_id, user, repo, settings)
    return {
        "id": project.id,
        "tenant_id": project.target_tenant_id,
        "sync_schedule_hours": project.sync_schedule_hours,
        "baseline_window_days": project.baseline_window_days,
    }


# ------------------------------------------------------------------
# Sync (project-scoped, delegates to existing logic)
# ------------------------------------------------------------------


@router.post("/sync/trigger")
async def trigger_sync(
    project_id: str,
    request: Request,
    full: bool = False,
    max_pages: int = Query(default=0, ge=0, description="Limit Graph API pages (0 = unlimited)"),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Trigger sync using the project's credentials."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="operator",
    )

    cache: ProjectRepoCache = request.app.state.project_repo_cache
    project_repo = await cache.get_repo(project.database_name)

    from app.pipelines.ingest_pipeline import IngestPipeline
    from app.services.crypto import CryptoService
    from app.services.graph_ingest import GraphIngestService
    from app.services.graph_roles import GraphRolesService

    crypto = CryptoService(settings)
    secret = crypto.decrypt(project.encrypted_client_secret)
    graph = GraphIngestService(
        settings, client_id=project.client_id, client_secret=secret, max_pages=max_pages,
    )
    roles_svc = GraphRolesService(graph)
    pipeline = IngestPipeline(project_repo, graph, roles_svc, scan_repo=repo)
    summary = await pipeline.run(project.target_tenant_id, full_sync=full)
    return summary


@router.get("/sync/status")
async def get_sync_status(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    audit_state = await project_repo.get_sync_state("audit_logs")
    signin_state = await project_repo.get_sync_state("sign_in_logs")
    return {"tenant_id": tid, "audit_logs": audit_state, "sign_in_logs": signin_state}


# ------------------------------------------------------------------
# PIM Sessions
# ------------------------------------------------------------------


@router.get("/pim-sessions")
async def list_pim_sessions(
    project_id: str,
    request: Request,
    pim_status: str | None = Query(default=None, alias="status"),
    principal_id: str | None = None,
    role_name: str | None = None,
    has_anomalies: bool | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_pim_sessions(
        status=pim_status,
        principal_id=principal_id,
        role_name=role_name,
        has_anomalies=has_anomalies,
        offset=offset,
        limit=size,
    )
    return {
        "items": [s.model_dump(mode="json") for s in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/pim-sessions/analytics")
async def get_pim_session_analytics(
    project_id: str,
    request: Request,
    days: int = Query(default=30, ge=7, le=90),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    return await project_repo.get_pim_session_analytics(days=days)


@router.get("/pim-sessions/active")
async def get_active_pim_sessions(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    items = await project_repo.get_active_pim_sessions()
    return {"items": [s.model_dump(mode="json") for s in items], "total": len(items)}


@router.get("/pim-sessions/{session_id}")
async def get_pim_session_detail(
    project_id: str,
    session_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    session = await project_repo.get_pim_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="PIM session not found")
    return session.model_dump(mode="json")


@router.get("/pim-sessions/{session_id}/events")
async def get_pim_session_events(
    project_id: str,
    session_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    session = await project_repo.get_pim_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="PIM session not found")
    offset = (page - 1) * size
    items, total = await project_repo.get_session_action_events(
        session.identity_id,
        session.activation_time,
        session.expiry_time,
        offset=offset,
        limit=size,
    )
    return {
        "items": [e.model_dump(mode="json") for e in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/identities/{identity_id}/pim-sessions")
async def get_identity_pim_sessions(
    project_id: str,
    identity_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.get_pim_sessions_for_identity(
        identity_id,
        offset=offset,
        limit=size,
    )
    return {
        "items": [s.model_dump(mode="json") for s in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.post("/pim-sessions/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pim_session_sync(
    project_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.pipelines.pim_session_pipeline import PimSessionPipeline
    from app.services.crypto import CryptoService
    from app.services.graph_ingest import GraphIngestService

    project = await validate_project_access(project_id, user, repo, settings)
    tid = project.target_tenant_id

    cache: ProjectRepoCache = request.app.state.project_repo_cache
    project_repo = await cache.get_repo(project.database_name)

    crypto = CryptoService(settings)
    secret = (
        crypto.decrypt(project.encrypted_client_secret) if project.encrypted_client_secret else ""
    )
    graph = GraphIngestService(
        settings,
        client_id=project.client_id or None,
        client_secret=secret or None,
    )
    pipeline = PimSessionPipeline(
        project_repo,
        graph,
        business_hours_start=settings.pim_session_business_hours_start,
        business_hours_end=settings.pim_session_business_hours_end,
        scan_repo=repo,
    )

    async def _run() -> None:
        await pipeline.run(
            tid,
            subscription_ids=project.azure_subscription_ids or None,
            backfill_days=settings.pim_session_backfill_days,
        )

    background_tasks.add_task(_run)
    return {"status": "accepted", "message": "PIM session sync started"}


# ------------------------------------------------------------------
# Access Path Analysis
# ------------------------------------------------------------------


@router.get("/access-paths")
async def list_access_paths(
    project_id: str,
    request: Request,
    min_risk: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    offset = (page - 1) * size
    items, total = await project_repo.list_access_path_analyses(
        min_risk=min_risk, offset=offset, limit=size
    )
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/access-paths/summary")
async def get_access_paths_summary(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    summary = await project_repo.get_access_path_summary()
    return summary.model_dump(mode="json")


@router.get("/identities/{identity_id}/access-paths")
async def get_identity_access_paths(
    project_id: str,
    identity_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    tid, project_repo = await _get_project_context(project_id, user, repo, request, settings)
    analysis = await project_repo.get_access_path_analysis_by_identity(identity_id)
    if analysis is None:
        return {"identity_id": identity_id, "paths": [], "total_paths": 0, "highest_risk": "none"}
    return analysis.model_dump(mode="json")
