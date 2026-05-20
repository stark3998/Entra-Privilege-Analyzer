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
        {"path": "/identity_id/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_BEST_PRACTICE_VIOLATIONS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/violation_type/?"},
        {"path": "/priority/?"},
        {"path": "/resolved/?"},
        {"path": "/detected_at/?"},
        {"path": "/identity_id/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_ROLE_RECOMMENDATIONS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/identity_type/?"},
        {"path": "/reduction_score/?"},
        {"path": "/identity_id/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_PIM_SESSIONS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/status/?"},
        {"path": "/activation_time/?"},
        {"path": "/principal_id/?"},
        {"path": "/role_name/?"},
        {"path": "/identity_id/?"},
        {"path": "/duration_minutes/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_BASELINES_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/identity_id/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_REMEDIATION_ACTIONS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/_ts/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_RISK_DETECTIONS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/_ts/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_MINIMAL_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_APP_REGISTRATIONS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/display_name/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_GROUPS_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/display_name/?"},
    ],
    "excludedPaths": [{"path": "/*"}, {"path": "/\"_etag\"/?"}],
}

_ACCESS_PATH_ANALYSES_INDEX: dict[str, Any] = {
    "indexingMode": "consistent",
    "includedPaths": [
        {"path": "/identity_id/?"},
        {"path": "/highest_risk/?"},
        {"path": "/total_paths/?"},
        {"path": "/critical_paths/?"},
        {"path": "/high_paths/?"},
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
    ContainerDef(name="tenant_configs", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
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
    ContainerDef(name="sync_state", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
    ContainerDef(
        name="role_recommendations",
        partition_key_path="/identity_id",
        indexing_policy=_ROLE_RECOMMENDATIONS_INDEX,
    ),
    ContainerDef(
        name="drift_alerts",
        partition_key_path="/identity_id",
        default_ttl=15552000,
        indexing_policy=_DRIFT_ALERTS_INDEX,
    ),
    ContainerDef(
        name="baselines",
        partition_key_path="/identity_id",
        default_ttl=7776000,
        indexing_policy=_BASELINES_INDEX,
    ),
    ContainerDef(
        name="best_practice_violations",
        partition_key_path="/id",
        indexing_policy=_BEST_PRACTICE_VIOLATIONS_INDEX,
    ),
    ContainerDef(name="narratives", partition_key_path="/id", default_ttl=86400, indexing_policy=_MINIMAL_INDEX),
    ContainerDef(
        name="app_registrations",
        partition_key_path="/id",
        indexing_policy=_APP_REGISTRATIONS_INDEX,
    ),
    ContainerDef(name="mfa_records", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
    ContainerDef(name="ca_policies", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
    ContainerDef(
        name="risk_detections",
        partition_key_path="/id",
        default_ttl=7776000,
        indexing_policy=_RISK_DETECTIONS_INDEX,
    ),
    ContainerDef(
        name="groups",
        partition_key_path="/id",
        indexing_policy=_GROUPS_INDEX,
    ),
    ContainerDef(name="access_reviews", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
    ContainerDef(name="sod_rules", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
    ContainerDef(name="custom_roles", partition_key_path="/id", indexing_policy=_MINIMAL_INDEX),
    ContainerDef(
        name="remediation_actions",
        partition_key_path="/id",
        default_ttl=15552000,
        indexing_policy=_REMEDIATION_ACTIONS_INDEX,
    ),
    ContainerDef(
        name="pim_sessions",
        partition_key_path="/identity_id",
        indexing_policy=_PIM_SESSIONS_INDEX,
    ),
    ContainerDef(
        name="access_path_analyses",
        partition_key_path="/identity_id",
        indexing_policy=_ACCESS_PATH_ANALYSES_INDEX,
    ),
    ContainerDef(name="scan_events", partition_key_path="/scanId", default_ttl=7776000, indexing_policy=_MINIMAL_INDEX),
]
