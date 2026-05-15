"""Event parsing extracted from backend/app/services/graph_ingest.py.

Produces plain dicts matching the ActionEvent Cosmos document schema so the
function app writes documents identical to the backend.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any


def _deterministic_id(*parts: str) -> str:
    raw = "|".join(parts)
    return str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))


def parse_audit_event(
    tenant_id: str, raw: dict[str, Any]
) -> tuple[dict[str, Any], str, str]:
    """Parse a raw audit log entry into an action-event dict.

    Returns ``(event_dict, actor_object_id, actor_display_name)``.
    """
    initiated_by = raw.get("initiatedBy", {})
    user_info = initiated_by.get("user") or {}
    app_info = initiated_by.get("app") or {}

    actor_id = user_info.get("id") or app_info.get("id") or "unknown"
    actor_name = (
        user_info.get("displayName")
        or app_info.get("displayName")
        or "Unknown"
    )

    targets = raw.get("targetResources", [])
    first_target = targets[0] if targets else {}

    event_id = _deterministic_id(tenant_id, raw.get("id", ""), "audit")

    timestamp_str = raw.get("activityDateTime", "")
    timestamp = (
        datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if timestamp_str
        else datetime.now(UTC)
    )

    identity_prefix = "ServicePrincipal" if app_info.get("id") else "User"
    identity_id = f"{identity_prefix}_{actor_id}"

    event: dict[str, Any] = {
        "id": event_id,
        "tenantId": tenant_id,
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "identity_display_name": actor_name,
        "action": raw.get("activityDisplayName", "Unknown"),
        "resource": first_target.get("displayName"),
        "resource_type": first_target.get("type"),
        "result": raw.get("result", "success"),
        "source": "audit_log",
        "correlation_id": raw.get("correlationId"),
        "ip_address": None,
        "timestamp": timestamp.isoformat(),
        "raw_data": raw,
    }
    return event, actor_id, actor_name


def parse_sign_in_event(
    tenant_id: str, raw: dict[str, Any]
) -> tuple[dict[str, Any], str, str]:
    """Parse a raw sign-in log entry into an action-event dict.

    Returns ``(event_dict, actor_object_id, actor_display_name)``.
    """
    actor_id = raw.get("userId", "unknown")
    actor_name = raw.get("userDisplayName", "Unknown")

    if not actor_id or actor_id == "00000000-0000-0000-0000-000000000000":
        actor_id = raw.get("appId", "unknown")
        actor_name = raw.get("appDisplayName", actor_name)
        identity_prefix = "ServicePrincipal"
    else:
        identity_prefix = "User"

    identity_id = f"{identity_prefix}_{actor_id}"

    event_id = _deterministic_id(tenant_id, raw.get("id", ""), "signin")

    timestamp_str = raw.get("createdDateTime", "")
    timestamp = (
        datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        if timestamp_str
        else datetime.now(UTC)
    )

    status_info = raw.get("status", {})
    result = "success" if status_info.get("errorCode", 0) == 0 else "failure"

    event: dict[str, Any] = {
        "id": event_id,
        "tenantId": tenant_id,
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "identity_display_name": actor_name,
        "action": "Sign-in",
        "resource": raw.get("resourceDisplayName"),
        "resource_type": "Application",
        "result": result,
        "source": "sign_in_log",
        "correlation_id": raw.get("correlationId"),
        "ip_address": raw.get("ipAddress"),
        "timestamp": timestamp.isoformat(),
        "raw_data": raw,
    }
    return event, actor_id, actor_name
