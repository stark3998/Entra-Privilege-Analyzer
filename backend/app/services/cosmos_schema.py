from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContainerDef:
    """Definition for a Cosmos DB container."""

    name: str
    partition_key_path: str
    default_ttl: int | None = None
    indexing_policy: dict[str, Any] | None = None


_ACTION_EVENTS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/timestamp/?"},
        {"path": "/action/?"},
        {"path": "/result/?"},
        {"path": "/source/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_IDENTITY_PROFILES_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/display_name/?"},
        {"path": "/identity_type/?"},
        {"path": "/risk_score/?"},
        {"path": "/upn/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_DRIFT_ALERTS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/severity/?"},
        {"path": "/status/?"},
        {"path": "/detected_at/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}


MASTER_CONTAINERS: list[ContainerDef] = [
    ContainerDef(name="projects", partition_key_path="/ownerId"),
    ContainerDef(name="project_members", partition_key_path="/projectId"),
    ContainerDef(name="scan_history", partition_key_path="/projectId"),
    ContainerDef(name="scan_schedules", partition_key_path="/projectId"),
    ContainerDef(name="alert_rules", partition_key_path="/projectId"),
]


PROJECT_CONTAINERS: list[ContainerDef] = [
    ContainerDef(name="tenant_configs", partition_key_path="/id"),
    ContainerDef(
        name="identity_profiles",
        partition_key_path="/id",
        indexing_policy=_IDENTITY_PROFILES_INDEX,
    ),
    ContainerDef(
        name="action_events",
        partition_key_path="/identity_id",
        default_ttl=7776000,
        indexing_policy=_ACTION_EVENTS_INDEX,
    ),
    ContainerDef(name="sync_state", partition_key_path="/id"),
    ContainerDef(name="role_recommendations", partition_key_path="/identity_id"),
    ContainerDef(
        name="drift_alerts",
        partition_key_path="/identity_id",
        indexing_policy=_DRIFT_ALERTS_INDEX,
    ),
    ContainerDef(name="baselines", partition_key_path="/identity_id"),
    ContainerDef(name="best_practice_violations", partition_key_path="/id"),
    ContainerDef(name="narratives", partition_key_path="/id", default_ttl=86400),
    ContainerDef(name="app_registrations", partition_key_path="/id"),
    ContainerDef(name="mfa_records", partition_key_path="/id"),
    ContainerDef(name="ca_policies", partition_key_path="/id"),
    ContainerDef(name="risk_detections", partition_key_path="/id"),
    ContainerDef(name="groups", partition_key_path="/id"),
    ContainerDef(name="access_reviews", partition_key_path="/id"),
    ContainerDef(name="sod_rules", partition_key_path="/id"),
    ContainerDef(name="custom_roles", partition_key_path="/id"),
    ContainerDef(name="remediation_actions", partition_key_path="/id"),
    ContainerDef(name="pim_sessions", partition_key_path="/identity_id"),
    ContainerDef(name="access_path_analyses", partition_key_path="/identity_id"),
    ContainerDef(name="scan_events", partition_key_path="/scanId", default_ttl=7776000),
]
