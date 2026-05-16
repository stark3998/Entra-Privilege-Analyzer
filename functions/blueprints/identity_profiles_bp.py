"""Identity profile batch processing activity.

Reads user/SP/role data from scan_staging, queries action_events from
Cosmos for each identity in a batch, merges observed actions, and upserts
the resulting IdentityProfile documents.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import azure.durable_functions as df

from blueprints.shared import RETRY_OPTIONS, cosmos_config
from utils.cosmos_writer import (
    query_action_events_for_identity,
    read_scan_staging,
    upsert_identity_profile,
)
from utils.log_context import set_scan_context

logger = logging.getLogger(__name__)

bp = df.Blueprint()


@bp.activity_trigger(input_name="payload")
def process_identity_batch_activity(payload: dict) -> dict:
    """Process a batch of identities: build and upsert IdentityProfile dicts.

    Expects payload keys:
    - actor_entries: list of [identity_id, display_name] pairs
    - scan_id, tenant_id, cosmos_endpoint, cosmos_key, cosmos_database
    """
    set_scan_context(payload)
    actor_entries: list[list[str]] = payload["actor_entries"]
    tenant_id = payload["tenant_id"]
    scan_id = payload["scan_id"]
    cfg = cosmos_config(payload)
    now = datetime.now(UTC).isoformat()

    logger.info(
        "process_identity_batch START | scan=%s | tenant=%s | batch_size=%d",
        scan_id, tenant_id, len(actor_entries),
    )
    activity_start = time.monotonic()

    # Load directory data from staging
    user_lookup = _build_lookup(
        read_scan_staging(cfg["endpoint"], cfg["key"], cfg["database"], scan_id, "users"),
    )
    sp_lookup = _build_lookup(
        read_scan_staging(cfg["endpoint"], cfg["key"], cfg["database"], scan_id, "service_principals"),
    )
    role_defs = read_scan_staging(
        cfg["endpoint"], cfg["key"], cfg["database"], scan_id, "role_definitions",
    )
    role_def_lookup: dict[str, str] = {
        d.get("id", ""): d.get("displayName", "Unknown Role") for d in role_defs
    }
    raw_assignments = read_scan_staging(
        cfg["endpoint"], cfg["key"], cfg["database"], scan_id, "role_assignments",
    )
    raw_eligibilities = read_scan_staging(
        cfg["endpoint"], cfg["key"], cfg["database"], scan_id, "role_eligibilities",
    )

    active_roles_map = _build_role_map(raw_assignments, role_def_lookup)
    eligible_roles_map = _build_role_map(raw_eligibilities, role_def_lookup, assignment_type="pim_eligible")

    logger.info(
        "process_identity_batch staging loaded | scan=%s | users=%d | sps=%d | role_defs=%d | assignments=%d | eligibilities=%d",
        scan_id, len(user_lookup), len(sp_lookup), len(role_defs),
        len(raw_assignments), len(raw_eligibilities),
    )

    processed = 0
    errors = 0

    for identity_id, display_name in actor_entries:
        try:
            _process_single_identity(
                cfg, tenant_id, identity_id, display_name, now,
                user_lookup, sp_lookup, active_roles_map, eligible_roles_map,
            )
            processed += 1
        except Exception as exc:
            logger.error(
                "Failed to process identity %s | scan=%s | error=%s",
                identity_id, scan_id, exc,
            )
            errors += 1

    elapsed_ms = (time.monotonic() - activity_start) * 1000
    logger.info(
        "process_identity_batch DONE | scan=%s | processed=%d | errors=%d | elapsed=%.0fms",
        scan_id, processed, errors, elapsed_ms,
    )

    return {"processed": processed, "errors": errors}


def _build_lookup(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items if "id" in item}


def _parse_datetime(val: str | None) -> str | None:
    if not val:
        return None
    try:
        datetime.fromisoformat(val.replace("Z", "+00:00"))
        return val
    except (ValueError, TypeError):
        return None


def _build_role_map(
    raw_items: list[dict[str, Any]],
    role_def_lookup: dict[str, str],
    assignment_type: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a map of principalId → list of role dicts."""
    role_map: dict[str, list[dict[str, Any]]] = {}

    for item in raw_items:
        principal_id = item.get("principalId", "")
        role_def_id = item.get("roleDefinitionId", "")
        scope = item.get("directoryScopeId", "/")
        role_name = role_def_lookup.get(role_def_id, "Unknown Role")
        member_type = item.get("memberType", "Direct")

        start_dt = _parse_datetime(item.get("startDateTime"))
        end_dt = _parse_datetime(item.get("endDateTime"))

        if assignment_type:
            a_type = assignment_type
            is_permanent = end_dt is None
        else:
            assignment_type_raw = item.get("assignmentType", "Assigned")
            if assignment_type_raw == "Activated":
                a_type = "pim_activated"
                is_permanent = False
            elif member_type == "Group":
                a_type = "group"
                is_permanent = end_dt is None
            else:
                a_type = "direct"
                is_permanent = end_dt is None

        role = {
            "role_id": role_def_id,
            "role_name": role_name,
            "scope": scope,
            "assignment_type": a_type,
            "is_permanent": is_permanent,
            "start_date": start_dt,
            "end_date": end_dt,
            "member_type": member_type,
        }
        if assignment_type == "pim_eligible":
            role["eligibility_schedule_id"] = item.get("roleEligibilityScheduleId")

        role_map.setdefault(principal_id, []).append(role)

    return role_map


def _process_single_identity(
    cfg: dict[str, str],
    tenant_id: str,
    identity_id: str,
    display_name: str,
    now: str,
    user_lookup: dict[str, dict[str, Any]],
    sp_lookup: dict[str, dict[str, Any]],
    active_roles_map: dict[str, list[dict[str, Any]]],
    eligible_roles_map: dict[str, list[dict[str, Any]]],
) -> None:
    parts = identity_id.split("_", 1)
    identity_type_str = parts[0] if len(parts) == 2 else "User"
    object_id = parts[1] if len(parts) == 2 else identity_id

    events = query_action_events_for_identity(
        cfg["endpoint"], cfg["key"], cfg["database"], tenant_id, identity_id,
    )

    observed_map: dict[str, dict[str, Any]] = {}
    for evt in events:
        action = evt.get("action", "")
        resource = evt.get("resource", "")
        key = f"{action}|{resource}"
        ts = evt.get("timestamp", now)

        if key in observed_map:
            oa = observed_map[key]
            oa["count"] += 1
            oa["first_seen"] = min(oa["first_seen"], ts)
            oa["last_seen"] = max(oa["last_seen"], ts)
        else:
            observed_map[key] = {
                "action": action,
                "resource": resource or None,
                "count": 1,
                "first_seen": ts,
                "last_seen": ts,
            }

    observed_actions = list(observed_map.values())
    current_roles = active_roles_map.get(object_id, [])
    eligible_roles = eligible_roles_map.get(object_id, [])

    event_timestamps = [e.get("timestamp", now) for e in events]
    first_seen = min(event_timestamps) if event_timestamps else now
    last_seen = max(event_timestamps) if event_timestamps else now

    upn = None
    app_id = None
    user_type = None
    external_user_state = None
    last_sign_in_at = None
    last_non_interactive_sign_in_at = None

    if identity_type_str == "User" and object_id in user_lookup:
        user_data = user_lookup[object_id]
        upn = user_data.get("userPrincipalName")
        user_type = user_data.get("userType")
        external_user_state = user_data.get("externalUserState")
        sign_in = user_data.get("signInActivity")
        if sign_in:
            last_sign_in_at = sign_in.get("lastSignInDateTime")
            last_non_interactive_sign_in_at = sign_in.get("lastNonInteractiveSignInDateTime")
    elif identity_type_str == "ServicePrincipal" and object_id in sp_lookup:
        sp_data = sp_lookup[object_id]
        app_id = sp_data.get("appId")

    profile = {
        "id": identity_id,
        "tenantId": tenant_id,
        "tenant_id": tenant_id,
        "identity_type": identity_type_str,
        "object_id": object_id,
        "display_name": display_name,
        "upn": upn,
        "app_id": app_id,
        "current_roles": current_roles,
        "eligible_roles": eligible_roles,
        "observed_actions": observed_actions,
        "risk_score": 0.0,
        "action_count": len(events),
        "last_seen": last_seen,
        "first_seen": first_seen,
        "created_at": now,
        "updated_at": now,
        "user_type": user_type,
        "external_user_state": external_user_state,
        "last_sign_in_at": last_sign_in_at,
        "last_non_interactive_sign_in_at": last_non_interactive_sign_in_at,
    }

    upsert_identity_profile(cfg["endpoint"], cfg["key"], cfg["database"], tenant_id, profile)
