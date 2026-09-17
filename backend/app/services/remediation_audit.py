"""Tamper-evident, append-only audit trail for remediation actions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.models.remediation import (
    RemediationAction,
    RemediationAuditEvent,
    RemediationAuditEventType,
    RemediationStatus,
)

_MAX_APPEND_ATTEMPTS = 3


def compute_event_hash(event: RemediationAuditEvent) -> str:
    """Compute the canonical SHA-256 hash for an audit event."""
    payload = event.model_dump(mode="json", exclude={"event_hash"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_event_chain(events: list[RemediationAuditEvent]) -> bool:
    """Verify sequence, linkage, and content hashes for an action's events."""
    previous_hash: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence:
            return False
        if event.previous_hash != previous_hash:
            return False
        if event.event_hash != compute_event_hash(event):
            return False
        previous_hash = event.event_hash
    return True


class RemediationAuditTrail:
    """Creates immutable lifecycle evidence through repository create operations."""

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    async def append(
        self,
        action: RemediationAction,
        event_type: RemediationAuditEventType,
        actor_id: str,
        status: RemediationStatus,
        details: dict[str, Any] | None = None,
    ) -> RemediationAuditEvent:
        """Append one hash-linked event, retrying sequence collisions."""
        for attempt in range(_MAX_APPEND_ATTEMPTS):
            latest = await self._repo.get_latest_remediation_audit_event(action.id)
            sequence = latest.sequence + 1 if latest else 1
            event = RemediationAuditEvent(
                id=f"{action.id}:{sequence:020}",
                action_id=action.id,
                project_id=action.project_id,
                tenant_id=action.tenant_id,
                sequence=sequence,
                event_type=event_type,
                actor_id=actor_id,
                status=status,
                occurred_at=datetime.now(UTC),
                correlation_id=action.correlation_id,
                details=details or {},
                previous_hash=latest.event_hash if latest else None,
                event_hash="",
            )
            event.event_hash = compute_event_hash(event)
            try:
                return await self._repo.create_remediation_audit_event(event)
            except ValueError:
                if attempt == _MAX_APPEND_ATTEMPTS - 1:
                    raise
        raise RuntimeError("Unable to append remediation audit event")
