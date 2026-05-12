# backend/app/services/graph_roles.py
from __future__ import annotations

import logging
from typing import Any

from app.models.identity import CurrentRole
from app.services.graph_ingest import GraphIngestService

logger = logging.getLogger(__name__)


class GraphRolesService:
    """Fetches and maps role assignments to identities."""

    def __init__(self, ingest: GraphIngestService) -> None:
        self._ingest = ingest

    async def get_identity_roles(self, tenant_id: str) -> dict[str, list[CurrentRole]]:
        """Return a mapping of objectId -> list[CurrentRole].

        Fetches role assignments and role definitions, joins them to build
        CurrentRole objects.
        """
        assignments = await self._ingest.fetch_role_assignments(tenant_id)
        definitions = await self._ingest.fetch_role_definitions(tenant_id)

        # Build a role_definition_id -> role_name lookup
        role_lookup: dict[str, str] = {}
        for defn in definitions:
            role_lookup[defn.get("id", "")] = defn.get("displayName", "Unknown Role")

        # Map principal_id -> list of CurrentRole
        result: dict[str, list[CurrentRole]] = {}
        for assignment in assignments:
            principal_id = assignment.get("principalId", "")
            role_def_id = assignment.get("roleDefinitionId", "")
            scope = assignment.get("directoryScopeId", "/")

            # Try to get role name from expanded roleDefinition or lookup
            role_def: dict[str, Any] = assignment.get("roleDefinition", {})
            role_name = role_def.get("displayName") or role_lookup.get(role_def_id, "Unknown Role")

            # Determine assignment type
            assignment_type = "direct"
            if assignment.get("memberType") == "Group":
                assignment_type = "group"

            role = CurrentRole(
                role_id=role_def_id,
                role_name=role_name,
                scope=scope,
                assignment_type=assignment_type,
                is_permanent=True,  # PIM eligibility needs beta API
            )

            if principal_id not in result:
                result[principal_id] = []
            result[principal_id].append(role)

        return result
