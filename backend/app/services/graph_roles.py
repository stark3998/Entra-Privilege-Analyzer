# backend/app/services/graph_roles.py
from __future__ import annotations

import logging
from datetime import datetime

from app.models.identity import CurrentRole
from app.services.graph_ingest import GraphIngestService

logger = logging.getLogger(__name__)


class GraphRolesService:
    """Fetches and maps role assignments and PIM eligibilities to identities."""

    def __init__(self, ingest: GraphIngestService) -> None:
        self._ingest = ingest

    async def get_identity_roles(
        self, tenant_id: str
    ) -> tuple[dict[str, list[CurrentRole]], dict[str, list[CurrentRole]]]:
        """Return (active_roles_map, eligible_roles_map) keyed by objectId.

        Uses PIM schedule instance APIs (GA v1.0) which are a superset of the
        legacy roleAssignments endpoint. Falls back to roleAssignments if the
        schedule APIs return 403 (missing RoleManagement.Read.All).
        """
        definitions = await self._ingest.fetch_role_definitions(tenant_id)
        role_lookup: dict[str, str] = {}
        for defn in definitions:
            role_lookup[defn.get("id", "")] = defn.get("displayName", "Unknown Role")

        active_map: dict[str, list[CurrentRole]] = {}
        eligible_map: dict[str, list[CurrentRole]] = {}

        try:
            assignments = await self._ingest.fetch_role_assignment_schedule_instances(tenant_id)
            eligibilities = await self._ingest.fetch_role_eligibility_schedule_instances(tenant_id)
        except Exception:
            logger.warning(
                "PIM schedule APIs unavailable for tenant %s, falling back to roleAssignments",
                tenant_id,
            )
            assignments = await self._ingest.fetch_role_assignments(tenant_id)
            eligibilities = []

        for item in assignments:
            principal_id = item.get("principalId", "")
            role_def_id = item.get("roleDefinitionId", "")
            scope = item.get("directoryScopeId", "/")
            role_name = role_lookup.get(role_def_id, "Unknown Role")

            assignment_type_raw = item.get("assignmentType", "Assigned")
            member_type = item.get("memberType", "Direct")

            start_dt = _parse_datetime(item.get("startDateTime"))
            end_dt = _parse_datetime(item.get("endDateTime"))

            if assignment_type_raw == "Activated":
                assignment_type = "pim_activated"
                is_permanent = False
            elif member_type == "Group":
                assignment_type = "group"
                is_permanent = end_dt is None
            else:
                assignment_type = "direct"
                is_permanent = end_dt is None

            role = CurrentRole(
                role_id=role_def_id,
                role_name=role_name,
                scope=scope,
                assignment_type=assignment_type,
                is_permanent=is_permanent,
                start_date=start_dt,
                end_date=end_dt,
                member_type=member_type,
            )
            active_map.setdefault(principal_id, []).append(role)

        for item in eligibilities:
            principal_id = item.get("principalId", "")
            role_def_id = item.get("roleDefinitionId", "")
            scope = item.get("directoryScopeId", "/")
            role_name = role_lookup.get(role_def_id, "Unknown Role")
            member_type = item.get("memberType", "Direct")

            start_dt = _parse_datetime(item.get("startDateTime"))
            end_dt = _parse_datetime(item.get("endDateTime"))

            role = CurrentRole(
                role_id=role_def_id,
                role_name=role_name,
                scope=scope,
                assignment_type="pim_eligible",
                is_permanent=end_dt is None,
                start_date=start_dt,
                end_date=end_dt,
                member_type=member_type,
                eligibility_schedule_id=item.get("roleEligibilityScheduleId"),
            )
            eligible_map.setdefault(principal_id, []).append(role)

        return active_map, eligible_map


def _parse_datetime(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
