# backend/app/models/narrative.py
"""Pydantic v2 models for executive dashboard and AI-generated narratives."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class NarrativeScope(StrEnum):
    """Scope of a generated narrative."""

    EXECUTIVE = "executive"
    IDENTITY = "identity"
    DRIFT = "drift"
    RECOMMENDATION = "recommendation"


class Narrative(BaseModel):
    """An AI-generated narrative cached in Cosmos DB."""

    model_config = ConfigDict(extra="ignore")

    id: str  # {scope}_{scope_id}
    tenant_id: str
    scope: NarrativeScope
    scope_id: str  # "tenant" for executive, identity_id for identity, etc.
    content: str
    generated_at: datetime
    expires_at: datetime  # 24h after generation


class DashboardSummary(BaseModel):
    """Aggregated dashboard summary for a tenant."""

    tenant_id: str
    total_identities: int
    total_actions: int
    identities_by_type: dict[str, int]
    avg_risk_score: float
    high_risk_count: int  # risk_score > 70
    drift_alerts_open: int
    drift_alerts_by_severity: dict[str, int]
    compliance_score: float
    top_risky_identities: list[dict[str, str | float]]  # top 10
    recommendations_count: int
    avg_reduction_score: float
    computed_at: datetime


class TrendPoint(BaseModel):
    """A single data point for a time-series trend."""

    date: str  # ISO date (YYYY-MM-DD)
    value: float


class DashboardTrends(BaseModel):
    """30-day trend data for the executive dashboard."""

    risk_score_trend: list[TrendPoint]
    drift_alerts_trend: list[TrendPoint]
    actions_trend: list[TrendPoint]


class AnalyticsData(BaseModel):
    """Aggregated analytics payload for the Analytics page."""

    tenant_id: str
    days: int

    total_actions: int
    unique_active_identities: int
    avg_actions_per_identity: float
    failed_action_pct: float
    new_identities_count: int

    daily_action_counts: list[TrendPoint]

    top_actions: list[dict[str, str | int]]
    most_active_identities: list[dict[str, str | int]]
    actions_by_source: dict[str, int]
    success_vs_failure: dict[str, int]
    top_resources: list[dict[str, str | int]]

    top_roles: list[dict[str, str | int]]
    permission_utilization: dict[str, int]
    permanent_vs_pim: dict[str, int]
    overprivileged_count: int

    violations_by_type: dict[str, int]
    stale_identity_counts: dict[str, int]
    credential_expiry_violations: list[dict[str, str]]
    recent_drift_alerts: list[dict[str, str | float | int | None]]

    computed_at: datetime
