# backend/app/data/permission_catalog.py
"""Loads and queries the shared/permission_mappings.json catalog."""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CATALOG_PATH = Path(__file__).resolve().parents[3] / "shared" / "permission_mappings.json"


@lru_cache(maxsize=1)
def get_permission_catalog() -> dict[str, Any]:
    """Load and cache the permission mappings JSON file."""
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def action_to_permission(action: str) -> str | None:
    """Map an audit-log operation name to a Graph permission.

    Returns ``None`` when the action has no known mapping.
    """
    catalog = get_permission_catalog()
    mapping: dict[str, str] = catalog.get("audit_operation_to_permission", {})
    return mapping.get(action)


def get_risk_weight(permission: str) -> str:
    """Return the risk weight label for a Graph permission.

    Defaults to ``"low"`` if the permission is not in the catalog.
    """
    catalog = get_permission_catalog()
    perms: dict[str, dict[str, str]] = catalog.get("graph_permissions", {})
    entry = perms.get(permission)
    if entry is not None:
        return entry.get("risk_weight", "low")
    return "low"


def get_risk_weight_numeric(permission: str) -> int:
    """Return a numeric risk score (1/3/7/10) for a Graph permission."""
    catalog = get_permission_catalog()
    weights: dict[str, int] = catalog.get("risk_weights", {})
    label = get_risk_weight(permission)
    return weights.get(label, 1)
