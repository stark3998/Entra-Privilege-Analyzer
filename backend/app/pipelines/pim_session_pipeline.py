from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from collections.abc import Awaitable, Callable
from typing import Any

from app.models.action import ActionEvent, ActionSource
from app.models.pim_session import (
    ApprovalInfo,
    PimSession,
    PimSessionScope,
    PimSessionStatus,
    SessionLocationInfo,
    TicketInfo,
)
from app.models.project import ScanRecord
from app.services.azure_rm_pim import AzureRmPimService
from app.services.cosmos import CosmosRepo
from app.services.graph_ingest import GraphIngestService
from app.services.pim_session_anomaly_detector import (
    PimSessionAnomalyDetector,
    compute_risk_score,
    extract_locations,
)

logger = logging.getLogger(__name__)


def _deterministic_id(
    tenant_id: str, principal_id: str, role_def_id: str, activation_iso: str,
) -> str:
    raw = f"{tenant_id}|{principal_id}|{role_def_id}|{activation_iso}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_iso_duration(duration: str) -> timedelta:
    """Parse ISO 8601 duration like PT8H, PT1H30M, P1D, etc."""
    match = re.match(
        r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or ""
    )
    if not match:
        return timedelta(hours=8)
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class PimSessionPipeline:
    """Orchestrates PIM session discovery, event backfill, and anomaly detection."""

    def __init__(
        self,
        repo: CosmosRepo,
        graph: GraphIngestService,
        arm_pim: AzureRmPimService | None = None,
        business_hours_start: int = 7,
        business_hours_end: int = 19,
        progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._repo = repo
        self._graph = graph
        self._arm_pim = arm_pim
        self._progress_callback = progress_callback
        self._detector = PimSessionAnomalyDetector(
            repo, business_hours_start, business_hours_end,
        )

    async def _emit_progress(self, payload: dict[str, Any]) -> None:
        if self._progress_callback is None:
            return
        await self._progress_callback(payload)

    async def _update_phase(
        self, scan: ScanRecord | None, status: str, items: int = 0,
    ) -> None:
        if scan is None:
            return
        for phase in scan.phases:
            if phase.name == "pim_sessions":
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
        subscription_ids: list[str] | None = None,
        scan_record: ScanRecord | None = None,
        backfill_days: int = 30,
    ) -> dict[str, Any]:
        start_time = time.monotonic()
        now = datetime.now(UTC)

        sync_state = await self._repo.get_sync_state(tenant_id, "pim_sessions")
        since: datetime | None = None
        if sync_state:
            last_ts = sync_state.get("last_sync")
            if last_ts:
                since = _parse_dt(last_ts)
        if since is None:
            since = now - timedelta(days=backfill_days)

        role_defs = await self._graph.fetch_role_definitions(tenant_id)
        role_lookup: dict[str, str] = {
            d.get("id", ""): d.get("displayName", "Unknown Role") for d in role_defs
        }
        await self._emit_progress({"type": "scan.progress", "message": f"Loaded {len(role_defs)} PIM role definitions.", "phase": "pim_sessions", "status": "running"})

        # 1. Fetch Entra ID PIM activation requests
        logger.info("Fetching Entra PIM activation requests for tenant %s", tenant_id)
        raw_requests = await self._graph.fetch_role_assignment_schedule_requests(
            tenant_id, since=since,
        )
        await self._emit_progress({"type": "scan.progress", "message": f"Fetched {len(raw_requests)} PIM activation requests.", "phase": "pim_sessions", "status": "running", "items_processed": len(raw_requests)})
        entra_sessions = self._parse_entra_requests(
            tenant_id, raw_requests, role_lookup, now,
        )

        # 2. Fetch Azure RBAC PIM activation requests
        rbac_sessions: list[PimSession] = []
        if self._arm_pim and subscription_ids:
            for sub_id in subscription_ids:
                logger.info(
                    "Fetching Azure RBAC PIM requests for subscription %s", sub_id,
                )
                rbac_role_lookup = await self._arm_pim.fetch_rbac_role_definitions(
                    tenant_id, sub_id,
                )
                rbac_raw = await self._arm_pim.fetch_rbac_assignment_schedule_requests(
                    tenant_id, sub_id, since=since,
                )
                rbac_sessions.extend(
                    self._parse_rbac_requests(
                        tenant_id, rbac_raw, rbac_role_lookup, sub_id, now,
                    )
                )

        all_sessions = entra_sessions + rbac_sessions
        sessions_processed = 0

        # 3. For each session: backfill events, detect anomalies, upsert
        for session in all_sessions:
            existing = await self._repo.get_pim_session(tenant_id, session.id)
            if existing and existing.last_event_sync_at:
                session.created_at = existing.created_at

            end_time = min(session.expiry_time, now)
            if session.activation_time > now:
                await self._repo.upsert_pim_session(tenant_id, session)
                sessions_processed += 1
                continue

            # Backfill audit events for this user during the session window
            audit_events = await self._graph.fetch_audit_events_for_user(
                tenant_id, session.principal_id,
                session.activation_time, end_time,
            )
            parsed_audit: list[ActionEvent] = []
            for raw in audit_events:
                evt, _, _ = GraphIngestService.parse_audit_event(tenant_id, raw)
                parsed_audit.append(evt)

            # Backfill sign-in events
            sign_in_raw = await self._graph.fetch_sign_ins_for_user(
                tenant_id, session.principal_id,
                session.activation_time, end_time,
            )

            session.audit_event_count = len(parsed_audit)
            session.sign_in_event_count = len(sign_in_raw)
            session.total_event_count = len(parsed_audit) + len(sign_in_raw)
            session.unique_actions = sorted(set(e.action for e in parsed_audit))
            session.locations = extract_locations(sign_in_raw)
            session.last_event_sync_at = now

            # Update status
            if session.expiry_time <= now:
                session.status = PimSessionStatus.EXPIRED
                session.is_active = False
            else:
                session.status = PimSessionStatus.ACTIVE
                session.is_active = True

            # Anomaly detection
            anomalies = await self._detector.detect(
                tenant_id, session, parsed_audit, sign_in_raw,
            )
            session.anomalies = anomalies
            session.risk_score = compute_risk_score(anomalies)

            await self._repo.upsert_pim_session(tenant_id, session)
            sessions_processed += 1
            if sessions_processed % 10 == 0 and sessions_processed > 0:
                await self._emit_progress({"type": "scan.progress", "message": f"Processed {sessions_processed}/{len(all_sessions)} PIM sessions.", "phase": "pim_sessions", "status": "running", "items_processed": sessions_processed})

        # Update sync state
        await self._repo.upsert_sync_state(tenant_id, "pim_sessions", {
            "last_sync": now.isoformat(),
            "sessions_processed": sessions_processed,
        })

        duration_ms = int((time.monotonic() - start_time) * 1000)
        summary = {
            "tenant_id": tenant_id,
            "sessions_processed": sessions_processed,
            "entra_sessions": len(entra_sessions),
            "rbac_sessions": len(rbac_sessions),
            "duration_ms": duration_ms,
        }
        logger.info("PIM session pipeline complete: %s", summary)
        return summary

    def _parse_entra_requests(
        self,
        tenant_id: str,
        raw_requests: list[dict[str, Any]],
        role_lookup: dict[str, str],
        now: datetime,
    ) -> list[PimSession]:
        sessions: list[PimSession] = []
        for req in raw_requests:
            status_val = req.get("status", "")
            if status_val not in ("Provisioned", "Granted"):
                continue

            principal_id = req.get("principalId", "")
            role_def_id = req.get("roleDefinitionId", "")
            scope = req.get("directoryScopeId", "/")

            schedule_info = req.get("scheduleInfo") or {}
            start_dt_str = schedule_info.get("startDateTime")
            activation_time = _parse_dt(start_dt_str) or _parse_dt(req.get("createdDateTime")) or now

            expiration = schedule_info.get("expiration") or {}
            end_dt_str = expiration.get("endDateTime")
            duration_str = expiration.get("duration")

            if end_dt_str:
                expiry_time = _parse_dt(end_dt_str) or (activation_time + timedelta(hours=8))
            elif duration_str:
                expiry_time = activation_time + _parse_iso_duration(duration_str)
            else:
                expiry_time = activation_time + timedelta(hours=8)

            duration_minutes = int((expiry_time - activation_time).total_seconds() / 60)

            role_name = role_lookup.get(role_def_id, "Unknown Role")
            role_def = req.get("roleDefinition") or {}
            if role_def.get("displayName"):
                role_name = role_def["displayName"]

            principal = req.get("principal") or {}
            display_name = principal.get("displayName", "Unknown")
            upn = principal.get("userPrincipalName")

            ticket_raw = req.get("ticketInfo") or {}
            ticket_info = TicketInfo(
                ticket_number=ticket_raw.get("ticketNumber"),
                ticket_system=ticket_raw.get("ticketSystem"),
            ) if ticket_raw.get("ticketNumber") else None

            approval_id = req.get("approvalId")
            approval_info = ApprovalInfo(
                approval_id=approval_id,
            ) if approval_id else None

            session_id = _deterministic_id(
                tenant_id, principal_id, role_def_id,
                activation_time.isoformat(),
            )

            sessions.append(PimSession(
                id=session_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_display_name=display_name,
                principal_upn=upn,
                identity_id=f"User_{principal_id}",
                role_definition_id=role_def_id,
                role_name=role_name,
                scope=scope,
                session_scope=PimSessionScope.ENTRA_DIRECTORY,
                activation_time=activation_time,
                expiry_time=expiry_time,
                duration_minutes=duration_minutes,
                status=PimSessionStatus.ACTIVE if expiry_time > now else PimSessionStatus.EXPIRED,
                is_active=expiry_time > now,
                justification=req.get("justification"),
                ticket_info=ticket_info,
                approval_info=approval_info,
                activation_request_id=req.get("id"),
                created_at=now,
                updated_at=now,
            ))

        return sessions

    def _parse_rbac_requests(
        self,
        tenant_id: str,
        raw_requests: list[dict[str, Any]],
        role_lookup: dict[str, str],
        subscription_id: str,
        now: datetime,
    ) -> list[PimSession]:
        sessions: list[PimSession] = []
        for req in raw_requests:
            props = req.get("properties") or {}
            request_type = props.get("requestType", "")
            if request_type != "SelfActivate":
                continue

            principal_id = props.get("principalId", "")
            role_def_id = props.get("roleDefinitionId", "")
            scope = props.get("scope", f"/subscriptions/{subscription_id}")

            schedule = props.get("scheduleInfo") or {}
            start_dt_str = schedule.get("startDateTime")
            activation_time = _parse_dt(start_dt_str) or _parse_dt(props.get("createdOn")) or now

            expiration = schedule.get("expiration") or {}
            end_dt_str = expiration.get("endDateTime")
            duration_str = expiration.get("duration")

            if end_dt_str:
                expiry_time = _parse_dt(end_dt_str) or (activation_time + timedelta(hours=8))
            elif duration_str:
                expiry_time = activation_time + _parse_iso_duration(duration_str)
            else:
                expiry_time = activation_time + timedelta(hours=8)

            duration_minutes = int((expiry_time - activation_time).total_seconds() / 60)
            role_name = role_lookup.get(role_def_id, "Unknown Role")

            ticket_raw = props.get("ticketInfo") or {}
            ticket_info = TicketInfo(
                ticket_number=ticket_raw.get("ticketNumber"),
                ticket_system=ticket_raw.get("ticketSystem"),
            ) if ticket_raw.get("ticketNumber") else None

            session_id = _deterministic_id(
                tenant_id, principal_id, role_def_id,
                activation_time.isoformat(),
            )

            sessions.append(PimSession(
                id=session_id,
                tenant_id=tenant_id,
                principal_id=principal_id,
                principal_display_name="",
                identity_id=f"User_{principal_id}",
                role_definition_id=role_def_id,
                role_name=role_name,
                scope=scope,
                session_scope=PimSessionScope.AZURE_RBAC,
                activation_time=activation_time,
                expiry_time=expiry_time,
                duration_minutes=duration_minutes,
                status=PimSessionStatus.ACTIVE if expiry_time > now else PimSessionStatus.EXPIRED,
                is_active=expiry_time > now,
                justification=props.get("justification"),
                ticket_info=ticket_info,
                activation_request_id=req.get("name"),
                created_at=now,
                updated_at=now,
            ))

        return sessions
