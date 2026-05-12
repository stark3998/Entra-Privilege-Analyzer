# backend/app/data/builtin_roles.py
"""Loads built-in role catalogs and finds best-matching roles for a permission set."""
from __future__ import annotations

import fnmatch
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models.role import BuiltInRoleMatch, RoleScope

logger = logging.getLogger(__name__)

_ENTRA_PATH = Path(__file__).resolve().parents[3] / "shared" / "builtin_roles_entra.json"
_AZURE_PATH = Path(__file__).resolve().parents[3] / "shared" / "builtin_roles_azure.json"


@lru_cache(maxsize=1)
def get_entra_roles() -> list[dict[str, Any]]:
    """Load and cache Entra ID built-in roles."""
    with open(_ENTRA_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return list(data.get("roles", []))


@lru_cache(maxsize=1)
def get_azure_roles() -> list[dict[str, Any]]:
    """Load and cache Azure RBAC built-in roles."""
    with open(_AZURE_PATH, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return list(data.get("roles", []))


def _wildcard_covers(pattern: str, target: str) -> bool:
    """Check if an Entra-style wildcard permission covers the target.

    Entra permissions use path-like segments with ``*`` and ``allTasks`` as wildcards.
    For example, ``microsoft.directory/*/allTasks`` covers
    ``microsoft.directory/users/password/update``.
    """
    # Normalise for comparison
    pattern_lower = pattern.lower()
    target_lower = target.lower()

    # Convert Entra patterns to fnmatch-compatible patterns:
    #   allTasks -> *   allProperties -> *   allEntities -> *
    glob_pattern = (
        pattern_lower
        .replace("alltasks", "*")
        .replace("allproperties", "*")
        .replace("allentities", "*")
    )

    return fnmatch.fnmatch(target_lower, glob_pattern)


def find_matching_entra_roles(
    required_permissions: set[str],
) -> list[BuiltInRoleMatch]:
    """Score each Entra built-in role against a set of required permissions.

    ``match_score`` = |intersection(role_perms, required)| / max(|required|, 1).
    Wildcard matching is used for Entra permissions.
    """
    roles = get_entra_roles()
    results: list[BuiltInRoleMatch] = []

    for role in roles:
        role_perms: list[str] = role.get("permissions", [])

        matched: set[str] = set()
        for req in required_permissions:
            for rp in role_perms:
                if _wildcard_covers(rp, req):
                    matched.add(req)
                    break

        # Excess = role permissions that don't cover any required permission
        excess: list[str] = []
        for rp in role_perms:
            covers_any = any(
                _wildcard_covers(rp, req) for req in required_permissions
            )
            if not covers_any:
                excess.append(rp)

        match_score = len(matched) / max(len(required_permissions), 1)

        results.append(
            BuiltInRoleMatch(
                role_id=role.get("id", ""),
                role_name=role.get("displayName", ""),
                scope=RoleScope.ENTRA,
                match_score=round(match_score, 4),
                permissions_matched=len(matched),
                permissions_total=len(role_perms),
                excess_permissions=excess,
            )
        )

    results.sort(key=lambda m: m.match_score, reverse=True)
    return results


def _azure_wildcard_covers(pattern: str, target: str) -> bool:
    """Check if an Azure RBAC wildcard action covers the target.

    Azure uses patterns like ``Microsoft.Compute/virtualMachines/*`` or ``*/read``.
    """
    return fnmatch.fnmatch(target.lower(), pattern.lower())


def find_matching_azure_roles(
    required_actions: set[str],
) -> list[BuiltInRoleMatch]:
    """Score each Azure RBAC built-in role against required actions + dataActions.

    ``match_score`` = |intersection(role_all_actions, required)| / max(|required|, 1).
    """
    roles = get_azure_roles()
    results: list[BuiltInRoleMatch] = []

    for role in roles:
        perms = role.get("permissions", {})
        role_actions: list[str] = perms.get("actions", [])
        role_data_actions: list[str] = perms.get("dataActions", [])
        all_role_actions = role_actions + role_data_actions

        matched: set[str] = set()
        for req in required_actions:
            for ra in all_role_actions:
                if _azure_wildcard_covers(ra, req):
                    matched.add(req)
                    break

        excess: list[str] = []
        for ra in all_role_actions:
            covers_any = any(
                _azure_wildcard_covers(ra, req) for req in required_actions
            )
            if not covers_any:
                excess.append(ra)

        match_score = len(matched) / max(len(required_actions), 1)

        results.append(
            BuiltInRoleMatch(
                role_id=role.get("id", ""),
                role_name=role.get("roleName", ""),
                scope=RoleScope.AZURE,
                match_score=round(match_score, 4),
                permissions_matched=len(matched),
                permissions_total=len(all_role_actions),
                excess_permissions=excess,
            )
        )

    results.sort(key=lambda m: m.match_score, reverse=True)
    return results
