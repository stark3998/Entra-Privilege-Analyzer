from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class AccessPathNodeType(StrEnum):
    USER = "user"
    SERVICE_PRINCIPAL = "service_principal"
    APPLICATION = "application"
    GROUP = "group"
    DIRECTORY_ROLE = "directory_role"
    APP_PERMISSION = "app_permission"


class AccessPathEdgeType(StrEnum):
    OWNS_APP = "owns_app"
    APP_HAS_SP = "app_has_sp"
    SP_HAS_APP_ROLE = "sp_has_app_role"
    SP_HAS_DIRECTORY_ROLE = "sp_has_directory_role"
    OWNS_GROUP = "owns_group"
    MEMBER_OF_GROUP = "member_of_group"
    GROUP_HAS_ROLE = "group_has_role"
    OWNS_SP = "owns_sp"
    HAS_DIRECTORY_ROLE = "has_directory_role"
    CAN_MODIFY_ANY_APP = "can_modify_any_app"


class AccessPathNode(BaseModel):
    id: str
    node_type: AccessPathNodeType
    display_name: str
    properties: dict[str, Any] = {}


class AccessPathEdge(BaseModel):
    edge_type: AccessPathEdgeType
    description: str


class AccessPathStep(BaseModel):
    node: AccessPathNode
    edge: AccessPathEdge | None = None


class AccessPath(BaseModel):
    id: str
    path_type: str
    risk_level: str
    steps: list[AccessPathStep]
    target_privilege: str
    description: str
    exploitability: str

    @staticmethod
    def compute_id(steps: list[AccessPathStep], path_type: str) -> str:
        raw = "|".join(s.node.id for s in steps) + "|" + path_type
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


class AccessPathAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    identity_id: str
    identity_display_name: str
    identity_type: str
    paths: list[AccessPath] = []
    total_paths: int = 0
    critical_paths: int = 0
    high_paths: int = 0
    medium_paths: int = 0
    highest_risk: str = "none"
    analyzed_at: datetime


class AccessPathSummary(BaseModel):
    total_identities_with_paths: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    top_path_types: list[dict[str, Any]] = []
