"""Strict read-only tool allowlists for the durable agent workflow."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from agent_framework import FunctionTool
from pydantic import Field

from agents.errors import AgentToolPolicyError, AgentWorkflowConfigurationError
from agents.models import PrivilegeAnalysisRequest, StrictModel

_FUNCTIONS_ROOT = Path(__file__).resolve().parents[1]
_SHARED_ROOT = next(
    (
        candidate
        for candidate in (
            _FUNCTIONS_ROOT / "shared",
            _FUNCTIONS_ROOT.parent / "shared",
        )
        if candidate.is_dir()
    ),
    _FUNCTIONS_ROOT / "shared",
)


class NoArguments(StrictModel):
    pass


class RolesQuery(StrictModel):
    include_eligible: bool = False
    limit: int = Field(default=25, ge=1, le=100)


class ActionsQuery(StrictModel):
    min_count: int = Field(default=1, ge=0)
    limit: int = Field(default=25, ge=1, le=100)


class SearchPermissionCatalogInput(StrictModel):
    query: str = Field(min_length=2, max_length=120)
    limit: int = Field(default=10, ge=1, le=25)


class SearchBuiltinRolesInput(StrictModel):
    scope: str = Field(pattern="^(entra|azure)$")
    query: str = Field(min_length=2, max_length=120)
    limit: int = Field(default=10, ge=1, le=25)


def _result_to_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _shared_json(filename: str) -> Any:
    path = _SHARED_ROOT / filename
    if not path.exists():
        raise AgentWorkflowConfigurationError(
            f"Shared data file '{filename}' was not found"
        )
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _permission_catalog() -> list[dict[str, Any]]:
    payload = _shared_json("permission_mappings.json")
    graph_permissions = payload.get("graph_permissions")
    if not isinstance(graph_permissions, dict):
        raise AgentWorkflowConfigurationError(
            "permission_mappings.json has no graph_permissions object"
        )

    catalog: list[dict[str, Any]] = []
    for permission, details in graph_permissions.items():
        actions = details.get("actions", [])
        catalog.append(
            {
                "permission": permission,
                "actions": list(actions) if isinstance(actions, list) else [],
                "risk_weight": details.get("risk_weight", "unknown"),
                "category": details.get("category", "unknown"),
                "evidence_id": f"permission:{permission}",
            }
        )
    return catalog


@lru_cache(maxsize=1)
def _builtin_roles(scope: str) -> list[dict[str, Any]]:
    if scope == "entra":
        payload = _shared_json("builtin_roles_entra.json")
        roles = payload.get("roles", [])
        return [
            {
                "role_id": role.get("id", ""),
                "role_name": role.get("displayName", ""),
                "description": role.get("description", ""),
                "permissions": list(role.get("permissions", [])),
                "scope": "entra",
                "evidence_id": f"builtin-role:entra:{role.get('id', '')}",
            }
            for role in roles
        ]

    payload = _shared_json("builtin_roles_azure.json")
    roles = payload.get("roles", [])
    normalized: list[dict[str, Any]] = []
    for role in roles:
        permissions = role.get("permissions", {}) or {}
        normalized.append(
            {
                "role_id": role.get("id", ""),
                "role_name": role.get("roleName", ""),
                "description": role.get("description", ""),
                "permissions": list(permissions.get("actions", [])),
                "scope": "azure",
                "evidence_id": f"builtin-role:azure:{role.get('id', '')}",
            }
        )
    return normalized


class WorkflowEvidenceTools:
    """Materialize read-only tools against a single workflow request."""

    def __init__(self, workflow: PrivilegeAnalysisRequest) -> None:
        self._workflow = workflow

    def get_subject_summary(self) -> dict[str, Any]:
        return {
            "workflow_id": self._workflow.workflow_id,
            "analysis_goal": self._workflow.analysis_goal,
            "subject": self._workflow.subject.model_dump(mode="json"),
            "evidence_window_days": self._workflow.evidence_window_days,
            "permission_hints": list(self._workflow.permission_hints),
            "governance_constraints": list(self._workflow.governance_constraints),
            "context": list(self._workflow.additional_context),
        }

    def list_roles(
        self, include_eligible: bool = False, limit: int = 25
    ) -> dict[str, Any]:
        roles = list(self._workflow.current_roles)
        if include_eligible:
            roles.extend(self._workflow.eligible_roles)
        sliced = roles[:limit]
        return {
            "count": len(sliced),
            "items": [
                {
                    **role.model_dump(mode="json"),
                    "evidence_id": f"role:{role.role_id}:{role.scope}",
                }
                for role in sliced
            ],
        }

    def list_observed_actions(
        self, min_count: int = 1, limit: int = 25
    ) -> dict[str, Any]:
        actions = [
            action
            for action in self._workflow.observed_actions
            if action.count >= min_count
        ]
        actions.sort(key=lambda item: (-item.count, item.action, item.resource or ""))
        sliced = actions[:limit]
        return {
            "count": len(sliced),
            "items": [
                {
                    **action.model_dump(mode="json"),
                    "evidence_id": f"action:{idx}",
                }
                for idx, action in enumerate(sliced, start=1)
            ],
        }

    def list_risk_signals(self) -> dict[str, Any]:
        return {
            "count": len(self._workflow.risk_signals),
            "items": [
                {
                    **signal.model_dump(mode="json"),
                    "evidence_id": f"risk:{signal.signal_id}",
                }
                for signal in self._workflow.risk_signals
            ],
        }

    def list_persona_candidates(self) -> dict[str, Any]:
        ordered = sorted(
            self._workflow.persona_candidates,
            key=lambda item: (-item.match_score, item.name),
        )
        return {
            "count": len(ordered),
            "items": [
                {
                    **persona.model_dump(mode="json"),
                    "evidence_id": f"persona:{persona.name}",
                }
                for persona in ordered
            ],
        }

    def list_governance_constraints(self) -> dict[str, Any]:
        return {
            "count": len(self._workflow.governance_constraints),
            "items": [
                {"constraint": value, "evidence_id": f"constraint:{idx}"}
                for idx, value in enumerate(
                    self._workflow.governance_constraints, start=1
                )
            ],
        }

    def search_permission_catalog(self, query: str, limit: int = 10) -> dict[str, Any]:
        lowered = query.lower()
        matches = [
            item
            for item in _permission_catalog()
            if lowered in item["permission"].lower()
            or lowered in item["category"].lower()
            or any(lowered in action.lower() for action in item["actions"])
        ]
        return {"count": min(len(matches), limit), "items": matches[:limit]}

    def search_builtin_roles(
        self, scope: str, query: str, limit: int = 10
    ) -> dict[str, Any]:
        lowered = query.lower()
        matches = [
            item
            for item in _builtin_roles(scope)
            if lowered in item["role_name"].lower()
            or lowered in item["description"].lower()
            or any(lowered in permission.lower() for permission in item["permissions"])
        ]
        return {"count": min(len(matches), limit), "items": matches[:limit]}

    def materialize(self, allowlist: tuple[str, ...]) -> list[FunctionTool]:
        builders = {
            "get_subject_summary": lambda: FunctionTool(
                name="get_subject_summary",
                description="Return the immutable workflow subject, goal, and analysis context.",
                func=self.get_subject_summary,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=4,
            ),
            "list_roles": lambda: FunctionTool(
                name="list_roles",
                description="List current roles and, optionally, eligible roles for the subject identity.",
                func=self.list_roles,
                input_model=RolesQuery,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=6,
            ),
            "list_observed_actions": lambda: FunctionTool(
                name="list_observed_actions",
                description="List observed privileged actions for the subject identity.",
                func=self.list_observed_actions,
                input_model=ActionsQuery,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=6,
            ),
            "list_risk_signals": lambda: FunctionTool(
                name="list_risk_signals",
                description="Return supplied risk detections and risk signals for the subject identity.",
                func=self.list_risk_signals,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=4,
            ),
            "list_persona_candidates": lambda: FunctionTool(
                name="list_persona_candidates",
                description="Return peer persona candidates and their baseline permissions.",
                func=self.list_persona_candidates,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=4,
            ),
            "list_governance_constraints": lambda: FunctionTool(
                name="list_governance_constraints",
                description="Return immutable governance constraints and operator notes for this workflow.",
                func=self.list_governance_constraints,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=3,
            ),
            "search_permission_catalog": lambda: FunctionTool(
                name="search_permission_catalog",
                description="Search the shared Graph permission mapping catalog by permission, action, or category.",
                func=self.search_permission_catalog,
                input_model=SearchPermissionCatalogInput,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=8,
            ),
            "search_builtin_roles": lambda: FunctionTool(
                name="search_builtin_roles",
                description="Search the shared Entra or Azure built-in role catalogs.",
                func=self.search_builtin_roles,
                input_model=SearchBuiltinRolesInput,
                approval_mode="never_require",
                result_parser=_result_to_json,
                max_invocations=8,
            ),
        }

        unknown = sorted(set(allowlist).difference(builders))
        if unknown:
            raise AgentToolPolicyError(
                f"Unknown or unauthorized tool(s): {', '.join(unknown)}"
            )

        return [builders[name]() for name in allowlist]
