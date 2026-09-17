"""Read-only Cosmos evidence access for scoped copilot queries."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from typing import Any

from azure.cosmos import CosmosClient
from pydantic import ValidationError

from agents.models import AgentQueryRequest, AgentQueryScope

_CLIENT_CACHE: dict[str, CosmosClient] = {}
_MASTER_CONTAINER = "projects"


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value


def _get_client(endpoint: str, key: str) -> CosmosClient:
    cache_key = f"{endpoint}:{sha256(key.encode()).hexdigest()}"
    if cache_key not in _CLIENT_CACHE:
        _CLIENT_CACHE[cache_key] = CosmosClient(endpoint, credential=key)
    return _CLIENT_CACHE[cache_key]


class ProjectEvidenceAccessor:
    """Resolve scoped, read-only evidence for one query request."""

    def __init__(self, request: AgentQueryRequest) -> None:
        self._request = request
        try:
            self._scope = AgentQueryScope.model_validate(request.scope)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid scope payload: {exc}") from exc

        endpoint = _required_env("COSMOS_ENDPOINT")
        key = _required_env("COSMOS_KEY")
        master_database = os.environ.get("COSMOS_MASTER_DATABASE") or _required_env(
            "COSMOS_DATABASE"
        )
        client = _get_client(endpoint, key)
        self._project = self._load_project(client, master_database)
        target_tenant_id = str(self._project.get("target_tenant_id") or "")
        if target_tenant_id != request.tenant_id:
            raise RuntimeError(
                f"Project {request.project_id} does not belong to the requested tenant"
            )
        self._database_name = str(self._project.get("database_name") or "").strip()
        if not self._database_name:
            raise RuntimeError(
                f"Project {request.project_id} does not have an assigned Cosmos database"
            )
        self._db = client.get_database_client(self._database_name)

    def get_project_summary(self) -> dict[str, Any]:
        return {
            "citation": self._project_citation(),
            "project_id": self._request.project_id,
            "project_name": self._project.get("name", ""),
            "target_tenant_id": self._project.get("target_tenant_id", ""),
            "target_tenant_name": self._project.get("target_tenant_name", ""),
            "last_scan_at": self._project.get("last_scan_at"),
            "last_scan_status": self._project.get("last_scan_status"),
            "identity_count": self._project.get("identity_count", 0),
            "risk_score": self._project.get("risk_score", 0.0),
            "scope": self._scope.model_dump(mode="json"),
        }

    def list_scope_evidence(self, limit: int = 8) -> dict[str, Any]:
        items: list[dict[str, Any]] = [self.get_project_summary()]
        if self._scope.evidence_ids:
            for evidence_id in self._scope.evidence_ids[:limit]:
                items.append(self.get_evidence_detail(evidence_id))
            return {"count": len(items), "items": items[:limit]}

        identity_id = self._scope.identity_id
        if identity_id:
            items.append(self.get_identity_profile(identity_id))
            recommendation = self._maybe_get_recommendation(identity_id)
            if recommendation is not None and self._scope.include_recommendations:
                items.append(recommendation)
            if self._scope.include_drift:
                items.extend(
                    self._list_drift_alerts(identity_id=identity_id, limit=limit)
                )
            if self._scope.include_best_practices:
                items.extend(
                    self._list_best_practice_violations(
                        identity_id=identity_id,
                        limit=limit,
                    )
                )
            return {"count": len(items[:limit]), "items": items[:limit]}

        items.extend(self._list_identities(limit=limit))
        if self._scope.include_drift:
            items.extend(self._list_drift_alerts(limit=max(1, limit // 2)))
        if self._scope.include_best_practices:
            items.extend(self._list_best_practice_violations(limit=max(1, limit // 2)))
        return {"count": len(items[:limit]), "items": items[:limit]}

    def search_evidence(self, query: str, limit: int = 8) -> dict[str, Any]:
        lowered = query.lower()
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in self.list_scope_evidence(limit=max(limit * 2, 8))["items"]:
            serialized = json.dumps(item, default=str).lower()
            evidence_id = str(item.get("citation", {}).get("evidence_id", ""))
            if lowered in serialized and evidence_id not in seen:
                seen.add(evidence_id)
                matches.append(item)

        for item in self._list_identities(limit=max(limit * 2, 8)):
            serialized = json.dumps(item, default=str).lower()
            evidence_id = str(item.get("citation", {}).get("evidence_id", ""))
            if lowered in serialized and evidence_id not in seen:
                seen.add(evidence_id)
                matches.append(item)

        return {"count": min(len(matches), limit), "items": matches[:limit]}

    def get_identity_profile(self, identity_id: str | None = None) -> dict[str, Any]:
        resolved = identity_id or self._scope.identity_id
        if not resolved:
            raise RuntimeError("identity_id is required for get_identity_profile")

        container = self._db.get_container_client("identity_profiles")
        try:
            item = container.read_item(item=resolved, partition_key=resolved)
        except Exception as exc:
            raise RuntimeError(f"Identity profile {resolved} was not found") from exc
        return {
            "citation": self._identity_citation(item),
            "identity": {
                "id": item.get("id"),
                "display_name": item.get("display_name"),
                "identity_type": item.get("identity_type"),
                "risk_score": item.get("risk_score", 0.0),
                "current_roles": item.get("current_roles", []),
                "eligible_roles": item.get("eligible_roles", []),
                "observed_actions": item.get("observed_actions", []),
                "last_seen": item.get("last_seen"),
                "entra_risk_level": item.get("entra_risk_level"),
                "active_risk_detections": item.get("active_risk_detections", []),
            },
        }

    def get_evidence_detail(self, evidence_id: str) -> dict[str, Any]:
        kind, first, second = self._parse_evidence_id(evidence_id)
        if kind == "project":
            return self.get_project_summary()
        if kind == "identity":
            return self.get_identity_profile(first)
        if kind == "recommendation":
            result = self._maybe_get_recommendation(first)
            if result is None:
                raise RuntimeError(
                    f"Recommendation evidence {evidence_id} was not found"
                )
            return result
        if kind == "drift":
            return self._get_drift_alert(first, second)
        if kind == "violation":
            return self._get_best_practice_violation(first)
        raise RuntimeError(f"Unsupported evidence identifier '{evidence_id}'")

    def validate_evidence_ids(self, evidence_ids: list[str]) -> None:
        for evidence_id in evidence_ids:
            self.get_evidence_detail(evidence_id)

    def _load_project(
        self, client: CosmosClient, master_database: str
    ) -> dict[str, Any]:
        container = client.get_database_client(master_database).get_container_client(
            _MASTER_CONTAINER
        )
        query = (
            "SELECT TOP 1 c.id, c.name, c.target_tenant_id, c.target_tenant_name, "
            "c.database_name, c.last_scan_at, c.last_scan_status, c.identity_count, c.risk_score "
            "FROM c WHERE c.id = @projectId"
        )
        items = list(
            container.query_items(
                query=query,
                parameters=[
                    {"name": "@projectId", "value": self._request.project_id},
                ],
                enable_cross_partition_query=True,
            )
        )
        if not items:
            raise RuntimeError(f"Project {self._request.project_id} was not found")
        project = items[0]
        if str(project.get("target_tenant_id")) != self._request.tenant_id:
            raise RuntimeError("Project tenant does not match query tenant")
        return project

    def _list_identities(self, limit: int) -> list[dict[str, Any]]:
        container = self._db.get_container_client("identity_profiles")
        query = (
            "SELECT TOP @limit c.id, c.display_name, c.identity_type, c.risk_score, "
            "c.current_roles, c.observed_actions, c.last_seen "
            "FROM c ORDER BY c.risk_score DESC"
        )
        items = list(
            container.query_items(
                query=query,
                parameters=[{"name": "@limit", "value": limit}],
                enable_cross_partition_query=True,
            )
        )
        return [
            {
                "citation": self._identity_citation(item),
                "identity": {
                    "id": item.get("id"),
                    "display_name": item.get("display_name"),
                    "identity_type": item.get("identity_type"),
                    "risk_score": item.get("risk_score", 0.0),
                    "current_roles": item.get("current_roles", []),
                    "observed_actions": item.get("observed_actions", []),
                    "last_seen": item.get("last_seen"),
                },
            }
            for item in items
        ]

    def _maybe_get_recommendation(self, identity_id: str) -> dict[str, Any] | None:
        container = self._db.get_container_client("role_recommendations")
        try:
            item = container.read_item(item=identity_id, partition_key=identity_id)
        except Exception:
            return None
        return {
            "citation": {
                "evidence_id": f"recommendation:{identity_id}",
                "label": f"Recommendation for {item.get('identity_display_name', identity_id)}",
                "source": "role_recommendations",
                "target_type": "role_recommendation",
                "target_id": identity_id,
            },
            "recommendation": {
                "identity_id": item.get("identity_id"),
                "identity_display_name": item.get("identity_display_name"),
                "required_permissions": item.get("required_permissions", []),
                "permission_gaps": item.get("permission_gaps", []),
                "best_builtin_match": item.get("best_builtin_match"),
                "alternative_builtins": item.get("alternative_builtins", []),
                "custom_role": item.get("custom_role"),
                "reduction_score": item.get("reduction_score"),
                "computed_at": item.get("computed_at"),
            },
        }

    def _list_drift_alerts(
        self,
        *,
        identity_id: str | None = None,
        limit: int,
    ) -> list[dict[str, Any]]:
        container = self._db.get_container_client("drift_alerts")
        if identity_id:
            query = (
                "SELECT TOP @limit c.id, c.identity_id, c.identity_display_name, c.drift_type, "
                "c.action, c.severity, c.status, c.details, c.detected_at "
                "FROM c WHERE c.identity_id = @identityId ORDER BY c.detected_at DESC"
            )
            parameters = [
                {"name": "@limit", "value": limit},
                {"name": "@identityId", "value": identity_id},
            ]
        else:
            query = (
                "SELECT TOP @limit c.id, c.identity_id, c.identity_display_name, c.drift_type, "
                "c.action, c.severity, c.status, c.details, c.detected_at "
                "FROM c ORDER BY c.detected_at DESC"
            )
            parameters = [{"name": "@limit", "value": limit}]
        items = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        return [self._drift_payload(item) for item in items]

    def _get_drift_alert(self, identity_id: str, alert_id: str) -> dict[str, Any]:
        container = self._db.get_container_client("drift_alerts")
        items = list(
            container.query_items(
                query=(
                    "SELECT TOP 1 c.id, c.identity_id, c.identity_display_name, c.drift_type, "
                    "c.action, c.severity, c.status, c.details, c.detected_at "
                    "FROM c WHERE c.identity_id = @identityId AND c.id = @alertId"
                ),
                parameters=[
                    {"name": "@identityId", "value": identity_id},
                    {"name": "@alertId", "value": alert_id},
                ],
                enable_cross_partition_query=True,
            )
        )
        if not items:
            raise RuntimeError(f"Drift alert {alert_id} was not found")
        return self._drift_payload(items[0])

    def _list_best_practice_violations(
        self,
        *,
        identity_id: str | None = None,
        limit: int,
    ) -> list[dict[str, Any]]:
        container = self._db.get_container_client("best_practice_violations")
        if identity_id:
            query = (
                "SELECT TOP @limit c.id, c.identity_id, c.identity_display_name, c.identity_type, "
                "c.violation_type, c.priority, c.title, c.description, c.remediation_steps, c.detected_at "
                "FROM c WHERE c.identity_id = @identityId ORDER BY c.detected_at DESC"
            )
            parameters = [
                {"name": "@limit", "value": limit},
                {"name": "@identityId", "value": identity_id},
            ]
        else:
            query = (
                "SELECT TOP @limit c.id, c.identity_id, c.identity_display_name, c.identity_type, "
                "c.violation_type, c.priority, c.title, c.description, c.remediation_steps, c.detected_at "
                "FROM c ORDER BY c.detected_at DESC"
            )
            parameters = [{"name": "@limit", "value": limit}]
        items = list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
        return [self._violation_payload(item) for item in items]

    def _get_best_practice_violation(self, violation_id: str) -> dict[str, Any]:
        container = self._db.get_container_client("best_practice_violations")
        items = list(
            container.query_items(
                query=(
                    "SELECT TOP 1 c.id, c.identity_id, c.identity_display_name, c.identity_type, "
                    "c.violation_type, c.priority, c.title, c.description, c.remediation_steps, c.detected_at "
                    "FROM c WHERE c.id = @id"
                ),
                parameters=[{"name": "@id", "value": violation_id}],
                enable_cross_partition_query=True,
            )
        )
        if not items:
            raise RuntimeError(f"Best practice violation {violation_id} was not found")
        return self._violation_payload(items[0])

    def _parse_evidence_id(self, evidence_id: str) -> tuple[str, str, str]:
        parts = evidence_id.split(":")
        if len(parts) < 2:
            raise RuntimeError(f"Malformed evidence identifier '{evidence_id}'")
        kind = parts[0]
        first = parts[1]
        second = parts[2] if len(parts) > 2 else ""
        return kind, first, second

    def _project_citation(self) -> dict[str, str]:
        return {
            "evidence_id": f"project:{self._request.project_id}",
            "label": str(self._project.get("name", self._request.project_id)),
            "source": "projects",
            "target_type": "project",
            "target_id": self._request.project_id,
        }

    @staticmethod
    def _identity_citation(item: dict[str, Any]) -> dict[str, str]:
        identity_id = str(item.get("id", ""))
        return {
            "evidence_id": f"identity:{identity_id}",
            "label": str(item.get("display_name", identity_id)),
            "source": "identity_profiles",
            "target_type": "identity_profile",
            "target_id": identity_id,
        }

    @staticmethod
    def _drift_payload(item: dict[str, Any]) -> dict[str, Any]:
        identity_id = str(item.get("identity_id", ""))
        alert_id = str(item.get("id", ""))
        return {
            "citation": {
                "evidence_id": f"drift:{identity_id}:{alert_id}",
                "label": str(item.get("drift_type", "drift")),
                "source": "drift_alerts",
                "target_type": "drift_alert",
                "target_id": alert_id,
            },
            "drift_alert": {
                "id": alert_id,
                "identity_id": identity_id,
                "identity_display_name": item.get("identity_display_name"),
                "drift_type": item.get("drift_type"),
                "action": item.get("action"),
                "severity": item.get("severity"),
                "status": item.get("status"),
                "details": item.get("details"),
                "detected_at": item.get("detected_at"),
            },
        }

    @staticmethod
    def _violation_payload(item: dict[str, Any]) -> dict[str, Any]:
        violation_id = str(item.get("id", ""))
        return {
            "citation": {
                "evidence_id": f"violation:{violation_id}",
                "label": str(item.get("title", violation_id)),
                "source": "best_practice_violations",
                "target_type": "best_practice_violation",
                "target_id": violation_id,
            },
            "violation": {
                "id": violation_id,
                "identity_id": item.get("identity_id"),
                "identity_display_name": item.get("identity_display_name"),
                "identity_type": item.get("identity_type"),
                "violation_type": item.get("violation_type"),
                "priority": item.get("priority"),
                "title": item.get("title"),
                "description": item.get("description"),
                "remediation_steps": item.get("remediation_steps", []),
                "detected_at": item.get("detected_at"),
            },
        }
