from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.models.access_path import (
    AccessPath,
    AccessPathAnalysis,
    AccessPathEdge,
    AccessPathEdgeType,
    AccessPathNode,
    AccessPathNodeType,
    AccessPathStep,
)
from app.models.app_registration import HIGH_RISK_APP_PERMISSION_GUIDS
from app.models.identity import IdentityProfile, IdentityType
from app.services.cosmos import CosmosRepo
from app.services.graph_ingest import GraphIngestService

logger = logging.getLogger(__name__)

_MS_GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"

ADMIN_ROLE_NAMES: set[str] = {
    "global administrator",
    "privileged role administrator",
    "privileged authentication administrator",
    "application administrator",
    "cloud application administrator",
    "security administrator",
    "user administrator",
    "exchange administrator",
    "sharepoint administrator",
    "conditional access administrator",
    "authentication administrator",
    "intune administrator",
}

CRITICAL_ROLE_NAMES: set[str] = {
    "global administrator",
    "privileged role administrator",
}

CRITICAL_PERMISSION_GUIDS: set[str] = {
    "9e3f62cf-ca93-4989-b6ce-bf83d28f9fe8",  # RoleManagement.ReadWrite.Directory
    "06b708a9-e830-4db3-a914-8e69da51d44f",  # AppRoleAssignment.ReadWrite.All
}

APP_MODIFY_ROLES: set[str] = {
    "application administrator",
    "cloud application administrator",
}

APP_MODIFY_PERMISSION_GUID = "1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9"  # Application.ReadWrite.All


class _TenantGraph:
    """In-memory graph of tenant relationships for path analysis."""

    def __init__(self) -> None:
        self.app_owners: dict[str, list[str]] = {}
        self.sp_owners: dict[str, list[str]] = {}
        self.group_owners: dict[str, list[str]] = {}
        self.group_roles: dict[str, list[str]] = {}
        self.identity_groups: dict[str, list[str]] = {}
        self.sp_by_app_id: dict[str, dict[str, Any]] = {}
        self.app_by_app_id: dict[str, dict[str, Any]] = {}
        self.sp_app_roles: dict[str, list[dict[str, Any]]] = {}
        self.sp_directory_roles: dict[str, list[str]] = {}
        self.app_role_id_to_name: dict[str, str] = {}
        self.identity_roles: dict[str, list[str]] = {}
        self.identity_lookup: dict[str, IdentityProfile] = {}
        self.sp_display_names: dict[str, str] = {}
        self.app_display_names: dict[str, str] = {}
        self.group_display_names: dict[str, str] = {}


class AccessPathAnalyzer:
    """Builds an in-memory directed graph and detects privilege escalation paths."""

    def __init__(
        self, repo: CosmosRepo, graph: GraphIngestService,
        progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._repo = repo
        self._graph = graph
        self._progress_callback = progress_callback

    async def _emit_progress(self, payload: dict[str, Any]) -> None:
        if self._progress_callback is None:
            return
        await self._progress_callback(payload)

    async def analyze_tenant(self, tenant_id: str) -> list[AccessPathAnalysis]:
        await self._emit_progress({"type": "scan.progress", "message": "Loading tenant graph for access path analysis.", "phase": "access_paths", "status": "running"})
        tg = await self._load_tenant_graph(tenant_id)
        await self._emit_progress({"type": "scan.progress", "message": f"Loaded {len(tg.identity_lookup)} identities, {len(tg.app_by_app_id)} apps, {len(tg.sp_by_app_id)} service principals.", "phase": "access_paths", "status": "running"})
        now = datetime.now(UTC)
        results: list[AccessPathAnalysis] = []

        for identity in tg.identity_lookup.values():
            obj_id = identity.object_id
            paths: list[AccessPath] = []

            paths.extend(self._find_app_ownership_paths(tg, identity, obj_id))
            paths.extend(self._find_group_paths(tg, identity, obj_id))
            paths.extend(self._find_sp_ownership_paths(tg, identity, obj_id))
            paths.extend(self._find_implicit_role_paths(tg, identity, obj_id))

            seen_ids: set[str] = set()
            deduped: list[AccessPath] = []
            for p in paths:
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    deduped.append(p)

            critical = sum(1 for p in deduped if p.risk_level == "critical")
            high = sum(1 for p in deduped if p.risk_level == "high")
            medium = sum(1 for p in deduped if p.risk_level == "medium")
            highest = "none"
            if critical:
                highest = "critical"
            elif high:
                highest = "high"
            elif medium:
                highest = "medium"

            analysis = AccessPathAnalysis(
                id=f"access_paths_{identity.id}",
                tenant_id=tenant_id,
                identity_id=identity.id,
                identity_display_name=identity.display_name,
                identity_type=identity.identity_type.value,
                paths=deduped,
                total_paths=len(deduped),
                critical_paths=critical,
                high_paths=high,
                medium_paths=medium,
                highest_risk=highest,
                analyzed_at=now,
            )
            if deduped:
                results.append(analysis)

        await self._emit_progress({"type": "scan.progress", "message": f"Found {len(results)} identities with privilege escalation paths.", "phase": "access_paths", "status": "running", "items_processed": len(results)})
        logger.info(
            "Access path analysis for tenant %s: %d identities with paths",
            tenant_id, len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_tenant_graph(self, tenant_id: str) -> _TenantGraph:
        tg = _TenantGraph()

        identities = await self._load_all_identities(tenant_id)
        await self._emit_progress({"type": "scan.progress", "message": f"Loaded {len(identities)} identities from database.", "phase": "access_paths", "status": "running"})
        for ident in identities:
            tg.identity_lookup[ident.object_id] = ident
            role_names = [r.role_name.lower() for r in ident.current_roles]
            tg.identity_roles[ident.object_id] = role_names
            for gm in ident.group_memberships:
                tg.identity_groups.setdefault(ident.object_id, []).append(gm.group_id)
            if ident.identity_type == IdentityType.SERVICE_PRINCIPAL:
                sp_roles = [r.role_name for r in ident.current_roles
                            if r.role_name.lower() in ADMIN_ROLE_NAMES]
                if sp_roles:
                    tg.sp_directory_roles[ident.object_id] = sp_roles
                tg.sp_display_names[ident.object_id] = ident.display_name

        apps, _ = await self._repo.list_app_registrations(tenant_id, offset=0, limit=5000)
        await self._emit_progress({"type": "scan.progress", "message": f"Loaded {len(apps)} app registrations.", "phase": "access_paths", "status": "running"})
        for app in apps:
            tg.app_by_app_id[app.app_id] = {"id": app.id, "display_name": app.display_name, "app_id": app.app_id}
            tg.app_display_names[app.id] = app.display_name
            owner_ids = [o.id for o in app.owners]
            if owner_ids:
                tg.app_owners[app.id] = owner_ids

        groups, _ = await self._repo.list_groups(tenant_id, offset=0, limit=5000)
        await self._emit_progress({"type": "scan.progress", "message": f"Loaded {len(groups)} groups.", "phase": "access_paths", "status": "running"})
        for grp in groups:
            tg.group_display_names[grp.id] = grp.display_name
            if grp.roles_assigned:
                tg.group_roles[grp.id] = grp.roles_assigned
            owner_ids = [o.id for o in grp.owners] if grp.owners else []
            if owner_ids:
                tg.group_owners[grp.id] = owner_ids

        sps_raw = await self._graph.fetch_service_principals(tenant_id)
        await self._emit_progress({"type": "scan.progress", "message": f"Fetched {len(sps_raw)} service principals from Graph.", "phase": "access_paths", "status": "running"})
        for sp in sps_raw:
            sp_id = sp.get("id", "")
            app_id = sp.get("appId", "")
            tg.sp_by_app_id[app_id] = sp
            tg.sp_display_names.setdefault(sp_id, sp.get("displayName", ""))

        ms_graph_sp = await self._graph.fetch_service_principal_by_app_id(
            tenant_id, _MS_GRAPH_APP_ID,
        )
        if ms_graph_sp:
            for role_def in ms_graph_sp.get("appRoles", []):
                role_id = role_def.get("id", "")
                role_value = role_def.get("value", "")
                if role_id:
                    tg.app_role_id_to_name[role_id] = role_value

        relevant_sp_ids = self._get_relevant_sp_ids(tg, sps_raw)
        await self._emit_progress({"type": "scan.progress", "message": f"Fetching metadata for {len(relevant_sp_ids)} service principals (owners + app roles).", "phase": "access_paths", "status": "running"})
        await self._fetch_sp_metadata(tenant_id, tg, relevant_sp_ids)
        await self._emit_progress({"type": "scan.progress", "message": f"Completed SP metadata fetch. {len(tg.sp_owners)} SPs have owners, {len(tg.sp_app_roles)} have app role assignments.", "phase": "access_paths", "status": "running"})

        return tg

    def _get_relevant_sp_ids(
        self, tg: _TenantGraph, sps_raw: list[dict[str, Any]],
    ) -> list[str]:
        owned_app_ids = set()
        for app_id, app_info in tg.app_by_app_id.items():
            if app_info["id"] in tg.app_owners:
                owned_app_ids.add(app_id)

        relevant: set[str] = set()
        for sp in sps_raw:
            sp_id = sp.get("id", "")
            app_id = sp.get("appId", "")
            if app_id in owned_app_ids:
                relevant.add(sp_id)
            if sp_id in tg.sp_directory_roles:
                relevant.add(sp_id)
        # Also include all SPs — we need their app role assignments to find targets
        for sp in sps_raw:
            relevant.add(sp.get("id", ""))

        return list(relevant)

    async def _fetch_sp_metadata(
        self, tenant_id: str, tg: _TenantGraph, sp_ids: list[str],
    ) -> None:
        sem = asyncio.Semaphore(10)

        async def fetch_one(sp_id: str) -> None:
            async with sem:
                try:
                    owners = await self._graph.fetch_service_principal_owners(tenant_id, sp_id)
                    owner_ids = [o.get("id", "") for o in owners if o.get("id")]
                    if owner_ids:
                        tg.sp_owners[sp_id] = owner_ids
                except Exception:
                    logger.debug("Failed to fetch owners for SP %s", sp_id)

                try:
                    assignments = await self._graph.fetch_service_principal_app_role_assignments(
                        tenant_id, sp_id,
                    )
                    if assignments:
                        tg.sp_app_roles[sp_id] = assignments
                except Exception:
                    logger.debug("Failed to fetch appRoleAssignments for SP %s", sp_id)

        await asyncio.gather(*(fetch_one(sp_id) for sp_id in sp_ids))

    async def _load_all_identities(self, tenant_id: str) -> list[IdentityProfile]:
        all_identities: list[IdentityProfile] = []
        offset = 0
        page_size = 200
        while True:
            items, total = await self._repo.list_identities(tenant_id, offset=offset, limit=page_size)
            all_identities.extend(items)
            if offset + page_size >= total:
                break
            offset += page_size
        return all_identities

    # ------------------------------------------------------------------
    # Path finders
    # ------------------------------------------------------------------

    def _find_app_ownership_paths(
        self, tg: _TenantGraph, identity: IdentityProfile, obj_id: str,
    ) -> list[AccessPath]:
        paths: list[AccessPath] = []
        for app_obj_id, owner_ids in tg.app_owners.items():
            if obj_id not in owner_ids:
                continue
            app_info = None
            for info in tg.app_by_app_id.values():
                if info["id"] == app_obj_id:
                    app_info = info
                    break
            if not app_info:
                continue

            app_id = app_info["app_id"]
            sp = tg.sp_by_app_id.get(app_id)
            if not sp:
                continue
            sp_id = sp.get("id", "")

            source_node = self._identity_node(identity)
            app_node = AccessPathNode(
                id=app_obj_id,
                node_type=AccessPathNodeType.APPLICATION,
                display_name=app_info["display_name"],
            )
            sp_node = AccessPathNode(
                id=sp_id,
                node_type=AccessPathNodeType.SERVICE_PRINCIPAL,
                display_name=sp.get("displayName", ""),
            )

            for assignment in tg.sp_app_roles.get(sp_id, []):
                role_id = assignment.get("appRoleId", "")
                perm_name = tg.app_role_id_to_name.get(role_id, role_id)
                if role_id not in HIGH_RISK_APP_PERMISSION_GUIDS:
                    continue

                target_node = AccessPathNode(
                    id=role_id,
                    node_type=AccessPathNodeType.APP_PERMISSION,
                    display_name=perm_name,
                    properties={"permission_id": role_id},
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=app_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.OWNS_APP, description="owns app registration")),
                    AccessPathStep(node=sp_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.APP_HAS_SP, description="has service principal")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.SP_HAS_APP_ROLE, description=f"has {perm_name}")),
                ]
                risk = "critical" if role_id in CRITICAL_PERMISSION_GUIDS else "high"
                path_id = AccessPath.compute_id(steps, "app_owner_to_app_perm")
                paths.append(AccessPath(
                    id=path_id,
                    path_type="app_owner_to_app_perm",
                    risk_level=risk,
                    steps=steps,
                    target_privilege=perm_name,
                    description=f"{identity.display_name} owns '{app_info['display_name']}' whose SP has {perm_name}",
                    exploitability="requires_credential_addition",
                ))

            for role_name in tg.sp_directory_roles.get(sp_id, []):
                target_node = AccessPathNode(
                    id=f"role_{role_name}",
                    node_type=AccessPathNodeType.DIRECTORY_ROLE,
                    display_name=role_name,
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=app_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.OWNS_APP, description="owns app registration")),
                    AccessPathStep(node=sp_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.APP_HAS_SP, description="has service principal")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.SP_HAS_DIRECTORY_ROLE, description=f"has {role_name}")),
                ]
                risk = "critical" if role_name.lower() in CRITICAL_ROLE_NAMES else "high"
                path_id = AccessPath.compute_id(steps, "app_owner_to_dir_role")
                paths.append(AccessPath(
                    id=path_id,
                    path_type="app_owner_to_dir_role",
                    risk_level=risk,
                    steps=steps,
                    target_privilege=role_name,
                    description=f"{identity.display_name} owns '{app_info['display_name']}' whose SP has {role_name}",
                    exploitability="requires_credential_addition",
                ))

        return paths

    def _find_group_paths(
        self, tg: _TenantGraph, identity: IdentityProfile, obj_id: str,
    ) -> list[AccessPath]:
        paths: list[AccessPath] = []
        source_node = self._identity_node(identity)

        for group_id, owner_ids in tg.group_owners.items():
            if obj_id not in owner_ids:
                continue
            roles = tg.group_roles.get(group_id, [])
            admin_roles = [r for r in roles if r.lower() in ADMIN_ROLE_NAMES]
            if not admin_roles:
                continue

            group_node = AccessPathNode(
                id=group_id,
                node_type=AccessPathNodeType.GROUP,
                display_name=tg.group_display_names.get(group_id, group_id),
            )
            for role_name in admin_roles:
                target_node = AccessPathNode(
                    id=f"role_{role_name}",
                    node_type=AccessPathNodeType.DIRECTORY_ROLE,
                    display_name=role_name,
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=group_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.OWNS_GROUP, description="owns group")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.GROUP_HAS_ROLE, description=f"has {role_name}")),
                ]
                risk = "critical" if role_name.lower() in CRITICAL_ROLE_NAMES else "high"
                path_id = AccessPath.compute_id(steps, "group_owner_to_role")
                paths.append(AccessPath(
                    id=path_id,
                    path_type="group_owner_to_role",
                    risk_level=risk,
                    steps=steps,
                    target_privilege=role_name,
                    description=f"{identity.display_name} owns group '{tg.group_display_names.get(group_id, '')}' which has {role_name}",
                    exploitability="requires_group_membership_change",
                ))

        for group_id in tg.identity_groups.get(obj_id, []):
            roles = tg.group_roles.get(group_id, [])
            admin_roles = [r for r in roles if r.lower() in ADMIN_ROLE_NAMES]
            if not admin_roles:
                continue

            group_node = AccessPathNode(
                id=group_id,
                node_type=AccessPathNodeType.GROUP,
                display_name=tg.group_display_names.get(group_id, group_id),
            )
            for role_name in admin_roles:
                target_node = AccessPathNode(
                    id=f"role_{role_name}",
                    node_type=AccessPathNodeType.DIRECTORY_ROLE,
                    display_name=role_name,
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=group_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.MEMBER_OF_GROUP, description="member of group")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.GROUP_HAS_ROLE, description=f"has {role_name}")),
                ]
                risk = "high"
                path_id = AccessPath.compute_id(steps, "group_member_to_role")
                paths.append(AccessPath(
                    id=path_id,
                    path_type="group_member_to_role",
                    risk_level=risk,
                    steps=steps,
                    target_privilege=role_name,
                    description=f"{identity.display_name} is member of group '{tg.group_display_names.get(group_id, '')}' which has {role_name}",
                    exploitability="direct",
                ))

        return paths

    def _find_sp_ownership_paths(
        self, tg: _TenantGraph, identity: IdentityProfile, obj_id: str,
    ) -> list[AccessPath]:
        paths: list[AccessPath] = []
        source_node = self._identity_node(identity)

        for sp_id, owner_ids in tg.sp_owners.items():
            if obj_id not in owner_ids:
                continue

            sp_node = AccessPathNode(
                id=sp_id,
                node_type=AccessPathNodeType.SERVICE_PRINCIPAL,
                display_name=tg.sp_display_names.get(sp_id, sp_id),
            )

            for assignment in tg.sp_app_roles.get(sp_id, []):
                role_id = assignment.get("appRoleId", "")
                perm_name = tg.app_role_id_to_name.get(role_id, role_id)
                if role_id not in HIGH_RISK_APP_PERMISSION_GUIDS:
                    continue
                target_node = AccessPathNode(
                    id=role_id,
                    node_type=AccessPathNodeType.APP_PERMISSION,
                    display_name=perm_name,
                    properties={"permission_id": role_id},
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=sp_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.OWNS_SP, description="owns service principal")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.SP_HAS_APP_ROLE, description=f"has {perm_name}")),
                ]
                risk = "critical" if role_id in CRITICAL_PERMISSION_GUIDS else "high"
                path_id = AccessPath.compute_id(steps, "sp_owner_to_app_perm")
                paths.append(AccessPath(
                    id=path_id, path_type="sp_owner_to_app_perm", risk_level=risk,
                    steps=steps, target_privilege=perm_name,
                    description=f"{identity.display_name} owns SP '{tg.sp_display_names.get(sp_id, '')}' which has {perm_name}",
                    exploitability="requires_credential_addition",
                ))

            for role_name in tg.sp_directory_roles.get(sp_id, []):
                target_node = AccessPathNode(
                    id=f"role_{role_name}",
                    node_type=AccessPathNodeType.DIRECTORY_ROLE,
                    display_name=role_name,
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=sp_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.OWNS_SP, description="owns service principal")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.SP_HAS_DIRECTORY_ROLE, description=f"has {role_name}")),
                ]
                risk = "critical" if role_name.lower() in CRITICAL_ROLE_NAMES else "high"
                path_id = AccessPath.compute_id(steps, "sp_owner_to_dir_role")
                paths.append(AccessPath(
                    id=path_id, path_type="sp_owner_to_dir_role", risk_level=risk,
                    steps=steps, target_privilege=role_name,
                    description=f"{identity.display_name} owns SP '{tg.sp_display_names.get(sp_id, '')}' which has {role_name}",
                    exploitability="requires_credential_addition",
                ))

        return paths

    def _find_implicit_role_paths(
        self, tg: _TenantGraph, identity: IdentityProfile, obj_id: str,
    ) -> list[AccessPath]:
        """P5: Application Administrator -> any app's SP permissions.
        P8: SP with Application.ReadWrite.All -> any app's SP permissions.
        Only targets critical privileges to avoid explosion.
        """
        paths: list[AccessPath] = []
        source_node = self._identity_node(identity)
        identity_role_names = set(tg.identity_roles.get(obj_id, []))

        has_app_admin = bool(identity_role_names & APP_MODIFY_ROLES)
        if not has_app_admin:
            return paths

        admin_role_name = next(iter(identity_role_names & APP_MODIFY_ROLES))
        role_node = AccessPathNode(
            id=f"role_{admin_role_name}",
            node_type=AccessPathNodeType.DIRECTORY_ROLE,
            display_name=admin_role_name.title(),
        )
        implicit_node = AccessPathNode(
            id="implicit_can_modify_any_app",
            node_type=AccessPathNodeType.APPLICATION,
            display_name="Any App Registration",
        )

        for app_id, app_info in tg.app_by_app_id.items():
            sp = tg.sp_by_app_id.get(app_id)
            if not sp:
                continue
            sp_id = sp.get("id", "")

            for assignment in tg.sp_app_roles.get(sp_id, []):
                role_id = assignment.get("appRoleId", "")
                if role_id not in CRITICAL_PERMISSION_GUIDS:
                    continue
                perm_name = tg.app_role_id_to_name.get(role_id, role_id)

                sp_node = AccessPathNode(
                    id=sp_id,
                    node_type=AccessPathNodeType.SERVICE_PRINCIPAL,
                    display_name=sp.get("displayName", ""),
                )
                target_node = AccessPathNode(
                    id=role_id,
                    node_type=AccessPathNodeType.APP_PERMISSION,
                    display_name=perm_name,
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=role_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.HAS_DIRECTORY_ROLE,
                        description=f"has {admin_role_name.title()}")),
                    AccessPathStep(node=implicit_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.CAN_MODIFY_ANY_APP,
                        description="can modify any app")),
                    AccessPathStep(node=sp_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.APP_HAS_SP,
                        description="has service principal")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.SP_HAS_APP_ROLE,
                        description=f"has {perm_name}")),
                ]
                path_id = AccessPath.compute_id(steps, "app_admin_to_critical_perm")
                paths.append(AccessPath(
                    id=path_id, path_type="app_admin_to_critical_perm", risk_level="critical",
                    steps=steps, target_privilege=perm_name,
                    description=f"{identity.display_name} has {admin_role_name.title()} and can add credentials to any app, reaching {perm_name}",
                    exploitability="requires_credential_addition",
                ))

            for role_name in tg.sp_directory_roles.get(sp_id, []):
                if role_name.lower() not in CRITICAL_ROLE_NAMES:
                    continue
                sp_node = AccessPathNode(
                    id=sp_id,
                    node_type=AccessPathNodeType.SERVICE_PRINCIPAL,
                    display_name=sp.get("displayName", ""),
                )
                target_node = AccessPathNode(
                    id=f"role_{role_name}",
                    node_type=AccessPathNodeType.DIRECTORY_ROLE,
                    display_name=role_name,
                )
                steps = [
                    AccessPathStep(node=source_node),
                    AccessPathStep(node=role_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.HAS_DIRECTORY_ROLE,
                        description=f"has {admin_role_name.title()}")),
                    AccessPathStep(node=implicit_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.CAN_MODIFY_ANY_APP,
                        description="can modify any app")),
                    AccessPathStep(node=sp_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.APP_HAS_SP,
                        description="has service principal")),
                    AccessPathStep(node=target_node, edge=AccessPathEdge(
                        edge_type=AccessPathEdgeType.SP_HAS_DIRECTORY_ROLE,
                        description=f"has {role_name}")),
                ]
                path_id = AccessPath.compute_id(steps, "app_admin_to_critical_role")
                paths.append(AccessPath(
                    id=path_id, path_type="app_admin_to_critical_role", risk_level="critical",
                    steps=steps, target_privilege=role_name,
                    description=f"{identity.display_name} has {admin_role_name.title()} and can add credentials to any app, reaching {role_name}",
                    exploitability="requires_credential_addition",
                ))

        return paths

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identity_node(identity: IdentityProfile) -> AccessPathNode:
        node_type = {
            IdentityType.USER: AccessPathNodeType.USER,
            IdentityType.SERVICE_PRINCIPAL: AccessPathNodeType.SERVICE_PRINCIPAL,
            IdentityType.MANAGED_IDENTITY: AccessPathNodeType.SERVICE_PRINCIPAL,
            IdentityType.GROUP: AccessPathNodeType.GROUP,
        }.get(identity.identity_type, AccessPathNodeType.USER)
        return AccessPathNode(
            id=identity.object_id,
            node_type=node_type,
            display_name=identity.display_name,
        )
