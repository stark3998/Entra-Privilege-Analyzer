# backend/app/pipelines/ingest_pipeline.py
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from app.models.action import ActionEvent
from app.models.identity import IdentityProfile, IdentityType, ObservedAction
from app.models.project import ScanRecord
from app.services.cosmos import CosmosRepo
from app.services.graph_ingest import GraphIngestService
from app.services.graph_roles import GraphRolesService

logger = logging.getLogger(__name__)


class IngestPipeline:
    """Orchestrates the full sync flow for a tenant."""

    def __init__(
        self,
        repo: CosmosRepo,
        graph: GraphIngestService,
        roles_svc: GraphRolesService,
    ) -> None:
        self._repo = repo
        self._graph = graph
        self._roles = roles_svc

    async def _update_phase(
        self, scan: ScanRecord | None, phase_name: str, status: str, items: int = 0,
    ) -> None:
        if scan is None:
            return
        for phase in scan.phases:
            if phase.name == phase_name:
                phase.status = status
                if status == "running":
                    phase.started_at = datetime.now(UTC)
                elif status in ("completed", "failed"):
                    phase.completed_at = datetime.now(UTC)
                    phase.items_processed = items
                break
        await self._repo.upsert_scan(scan)

    async def run(
        self,
        tenant_id: str,
        full_sync: bool = False,
        scan_record: ScanRecord | None = None,
    ) -> dict[str, Any]:
        start_time = time.monotonic()
        now = datetime.now(UTC)

        # 1. Load sync state
        audit_state = await self._repo.get_sync_state(tenant_id, "audit_logs")
        signin_state = await self._repo.get_sync_state(tenant_id, "sign_in_logs")

        delta_link: str | None = None
        signin_since: datetime | None = None

        if not full_sync:
            if audit_state:
                delta_link = audit_state.get("delta_link")
            if signin_state:
                last_ts = signin_state.get("last_sync")
                if last_ts:
                    signin_since = datetime.fromisoformat(last_ts)

        # 2. Fetch audit logs
        await self._update_phase(scan_record, "audit_logs", "running")
        logger.info("Fetching audit logs for tenant %s (full=%s)", tenant_id, full_sync)
        raw_audit_events, new_delta_link = await self._graph.fetch_audit_logs(
            tenant_id, delta_link=delta_link if not full_sync else None
        )
        await self._update_phase(scan_record, "audit_logs", "completed", len(raw_audit_events))

        # 3. Fetch sign-in logs
        await self._update_phase(scan_record, "sign_in_logs", "running")
        logger.info("Fetching sign-in logs for tenant %s", tenant_id)
        raw_signin_events = await self._graph.fetch_sign_in_logs(
            tenant_id, since=signin_since if not full_sync else None
        )
        await self._update_phase(scan_record, "sign_in_logs", "completed", len(raw_signin_events))

        # 4. Parse events, extract actor identities
        all_events: list[ActionEvent] = []
        actor_registry: dict[str, tuple[str, str]] = {}

        for raw in raw_audit_events:
            event, actor_id, actor_name = GraphIngestService.parse_audit_event(
                tenant_id, raw
            )
            all_events.append(event)
            if actor_id != "unknown":
                actor_registry[event.identity_id] = (actor_name, event.identity_id)

        for raw in raw_signin_events:
            event, actor_id, actor_name = GraphIngestService.parse_sign_in_event(
                tenant_id, raw
            )
            all_events.append(event)
            if actor_id != "unknown":
                actor_registry[event.identity_id] = (actor_name, event.identity_id)

        # 5. Fetch role assignments (PIM-aware) and user/SP enrichment data
        await self._update_phase(scan_record, "role_assignments", "running")
        logger.info("Fetching role assignments for tenant %s", tenant_id)
        active_roles_map, eligible_roles_map = await self._roles.get_identity_roles(tenant_id)
        await self._update_phase(scan_record, "role_assignments", "completed", len(active_roles_map))

        # Fetch users and SPs for enrichment (UPN, app_id, user_type)
        users_raw = await self._graph.fetch_users(tenant_id)
        sps_raw = await self._graph.fetch_service_principals(tenant_id)

        user_lookup: dict[str, dict[str, Any]] = {u["id"]: u for u in users_raw if "id" in u}
        sp_lookup: dict[str, dict[str, Any]] = {sp["id"]: sp for sp in sps_raw if "id" in sp}

        # 6. For each identity, create/update profile
        await self._update_phase(scan_record, "identity_profiles", "running")
        identities_processed = 0
        for identity_id, (display_name, _) in actor_registry.items():
            parts = identity_id.split("_", 1)
            identity_type_str = parts[0] if len(parts) == 2 else "User"
            object_id = parts[1] if len(parts) == 2 else identity_id

            try:
                identity_type = IdentityType(identity_type_str)
            except ValueError:
                identity_type = IdentityType.USER

            existing = await self._repo.get_identity(tenant_id, identity_id)

            identity_events = [e for e in all_events if e.identity_id == identity_id]

            # Merge observed actions
            observed_map: dict[str, ObservedAction] = {}
            if existing:
                for oa in existing.observed_actions:
                    key = f"{oa.action}|{oa.resource or ''}"
                    observed_map[key] = oa

            for evt in identity_events:
                key = f"{evt.action}|{evt.resource or ''}"
                if key in observed_map:
                    oa = observed_map[key]
                    observed_map[key] = ObservedAction(
                        action=oa.action,
                        resource=oa.resource,
                        count=oa.count + 1,
                        first_seen=min(oa.first_seen, evt.timestamp),
                        last_seen=max(oa.last_seen, evt.timestamp),
                    )
                else:
                    observed_map[key] = ObservedAction(
                        action=evt.action,
                        resource=evt.resource,
                        count=1,
                        first_seen=evt.timestamp,
                        last_seen=evt.timestamp,
                    )

            observed_actions = list(observed_map.values())
            current_roles = active_roles_map.get(object_id, [])
            eligible_roles = eligible_roles_map.get(object_id, [])

            # Timestamps
            event_timestamps = [e.timestamp for e in identity_events]
            earliest_event = min(event_timestamps) if event_timestamps else now
            latest_event = max(event_timestamps) if event_timestamps else now

            if existing:
                first_seen = (
                    min(existing.first_seen, earliest_event)
                    if existing.first_seen
                    else earliest_event
                )
                last_seen = (
                    max(existing.last_seen, latest_event)
                    if existing.last_seen
                    else latest_event
                )
                created_at = existing.created_at
                total_action_count = existing.action_count + len(identity_events)
            else:
                first_seen = earliest_event
                last_seen = latest_event
                created_at = now
                total_action_count = len(identity_events)

            # Enrich UPN and app_id from user/SP lookups
            upn: str | None = None
            app_id: str | None = None
            user_type: str | None = None
            external_user_state: str | None = None

            if identity_type == IdentityType.USER and object_id in user_lookup:
                user_data = user_lookup[object_id]
                upn = user_data.get("userPrincipalName")
                user_type = user_data.get("userType")
                external_user_state = user_data.get("externalUserState")
            elif identity_type == IdentityType.SERVICE_PRINCIPAL and object_id in sp_lookup:
                sp_data = sp_lookup[object_id]
                app_id = sp_data.get("appId")

            if existing:
                upn = upn or existing.upn
                app_id = app_id or existing.app_id
                user_type = user_type or existing.user_type
                external_user_state = external_user_state or existing.external_user_state

            profile = IdentityProfile(
                id=identity_id,
                tenant_id=tenant_id,
                identity_type=identity_type,
                object_id=object_id,
                display_name=display_name,
                upn=upn,
                app_id=app_id,
                current_roles=current_roles,
                eligible_roles=eligible_roles,
                observed_actions=observed_actions,
                risk_score=0.0,
                action_count=total_action_count,
                last_seen=last_seen,
                first_seen=first_seen,
                created_at=created_at,
                updated_at=now,
                user_type=user_type,
                external_user_state=external_user_state,
            )
            await self._repo.upsert_identity(tenant_id, profile)
            identities_processed += 1

        await self._update_phase(scan_record, "identity_profiles", "completed", identities_processed)

        # 7. Bulk insert action events
        await self._update_phase(scan_record, "action_events", "running")
        events_inserted = await self._repo.append_action_events(tenant_id, all_events)
        await self._update_phase(scan_record, "action_events", "completed", events_inserted)

        # 8. Update sync state
        await self._repo.upsert_sync_state(tenant_id, "audit_logs", {
            "delta_link": new_delta_link,
            "last_sync": now.isoformat(),
            "events_count": len(raw_audit_events),
        })
        await self._repo.upsert_sync_state(tenant_id, "sign_in_logs", {
            "last_sync": now.isoformat(),
            "events_count": len(raw_signin_events),
        })

        duration_ms = int((time.monotonic() - start_time) * 1000)

        summary: dict[str, Any] = {
            "tenant_id": tenant_id,
            "full_sync": full_sync,
            "identities_processed": identities_processed,
            "events_ingested": events_inserted,
            "audit_events_fetched": len(raw_audit_events),
            "signin_events_fetched": len(raw_signin_events),
            "duration_ms": duration_ms,
        }
        logger.info("Ingest pipeline complete: %s", summary)
        return summary
