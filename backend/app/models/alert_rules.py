# backend/app/models/alert_rules.py
"""Pydantic v2 models for alert rules and scan scheduling."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AlertChannelType(StrEnum):
    """Supported notification channel types."""

    EMAIL = "email"
    TEAMS = "teams"
    WEBHOOK = "webhook"


class AlertRuleType(StrEnum):
    """Types of alert rules."""

    THRESHOLD = "threshold"
    EVENT = "event"
    DIGEST = "digest"


class AlertChannel(BaseModel):
    """Notification channel configuration for an alert rule."""

    channel_type: AlertChannelType
    config: dict[str, str | list[str]] = {}


class AlertRule(BaseModel):
    """A configured alert rule for a project."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    project_id: str
    name: str
    rule_type: AlertRuleType
    condition: str = ""  # e.g. "compliance_score < 80", "new_critical_violation"
    severity_filter: list[str] = []  # ["critical", "high"]
    channel: AlertChannel
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class ScanSchedule(BaseModel):
    """Scheduled scan configuration for a project."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    project_id: str
    schedule_type: str = "daily"  # daily | weekly | custom
    cron_expression: str | None = None
    job_types: list[str] = ["full_sync", "best_practice_evaluation"]
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
