from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TenantRegistryEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    display_name: str = ""
    database_name: str
    status: Literal["provisioning", "active", "error"] = "provisioning"
    project_ids: list[str] = Field(default_factory=list)
    raw_activity_retention_days: int = 365
    legal_hold: bool = False
    created_at: datetime
    updated_at: datetime


class EvidenceNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    node_type: str
    source_id: str
    display_name: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime
    valid_to: datetime | None = None
    observed_at: datetime
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EntitlementEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    principal_id: str
    entitlement_id: str
    edge_type: str
    scope_id: str | None = None
    assignment_id: str | None = None
    source: str
    provenance: list[str] = Field(default_factory=list)
    condition: str | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    observed_at: datetime
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EvidenceLineage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    evidence_id: str
    tenant_id: str
    source: str
    source_record_id: str
    scan_id: str
    collected_at: datetime
    normalized_at: datetime
    transformation_version: str
    source_watermark: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ActivityEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    principal_id: str
    action: str
    source: str
    occurred_at: datetime
    resource_id: str | None = None
    resource_type: str | None = None
    result: str = "success"
    correlation_id: str | None = None
    evidence_id: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    ttl: int | None = None


class ActionFeatureAggregate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    principal_id: str
    action: str
    bucket: Literal["hour", "day", "week"]
    bucket_start: datetime
    count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    failure_count: int = Field(default=0, ge=0)
    distinct_resource_count: int = Field(default=0, ge=0)
    first_seen: datetime
    last_seen: datetime
    seasonal_baseline: float | None = None


class CollectionCursor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source: str
    tenant_id: str
    cursor: str | None = None
    watermark: datetime | None = None
    updated_at: datetime
    status: Literal["ready", "running", "throttled", "failed"] = "ready"
    error: str | None = None


class DataQualityStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source: str
    tenant_id: str
    assessed_at: datetime
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    gaps: list[str] = Field(default_factory=list)
