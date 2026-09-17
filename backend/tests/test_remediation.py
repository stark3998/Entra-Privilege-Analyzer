from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.remediation import (
    RemediationAction,
    RemediationActionType,
    RemediationAuditEvent,
    RemediationAuditEventType,
    RemediationStatus,
)
from app.services.provider_errors import (
    ProviderFailureCategory,
    ProviderOperationError,
    ProviderOperationResult,
)
from app.services.remediation_audit import verify_event_chain
from app.services.remediation_engine import RemediationEngine


class InMemoryRemediationRepo:
    def __init__(self) -> None:
        self.actions: dict[str, RemediationAction] = {}
        self.events: dict[str, list[RemediationAuditEvent]] = {}

    async def upsert_remediation_action(
        self,
        action: RemediationAction,
    ) -> RemediationAction:
        self.actions[action.id] = action
        return action

    async def get_remediation_action(self, action_id: str) -> RemediationAction | None:
        return self.actions.get(action_id)

    async def get_remediation_action_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> RemediationAction | None:
        return next(
            (
                action
                for action in self.actions.values()
                if action.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_latest_remediation_audit_event(
        self,
        action_id: str,
    ) -> RemediationAuditEvent | None:
        events = self.events.get(action_id, [])
        return events[-1] if events else None

    async def create_remediation_audit_event(
        self,
        event: RemediationAuditEvent,
    ) -> RemediationAuditEvent:
        events = self.events.setdefault(event.action_id, [])
        if any(existing.id == event.id for existing in events):
            raise ValueError("Audit event already exists")
        events.append(event)
        return event


class SuccessfulProvider:
    async def execute(
        self,
        action: RemediationAction,
        access_token: str,
    ) -> ProviderOperationResult:
        assert access_token == "obo-token"
        return ProviderOperationResult(
            provider="microsoft-graph",
            operation_id=f"operation-{action.id}",
            request_id="request-id",
            details={"verified": True},
        )


class ThrottledProvider:
    async def execute(
        self,
        action: RemediationAction,
        access_token: str,
    ) -> ProviderOperationResult:
        raise ProviderOperationError.from_http_status(
            429,
            "Provider throttled the request",
            provider="microsoft-graph",
            request_id="request-id",
        )


async def _approved_action(
    engine: RemediationEngine,
) -> RemediationAction:
    action = await engine.request_action(
        tenant_id="tenant-id",
        project_id="project-id",
        action_type=RemediationActionType.REMOVE_ROLE,
        target_identity_id="identity-id",
        requested_by="requester@example.com",
        justification="Least privilege",
        idempotency_key="request-key",
        correlation_id="correlation-id",
    )
    return await engine.approve_action(
        "tenant-id",
        action.id,
        "approver@example.com",
    )


@pytest.mark.asyncio
async def test_successful_execution_creates_valid_audit_chain() -> None:
    repo = InMemoryRemediationRepo()
    engine = RemediationEngine(repo, SuccessfulProvider())
    action = await _approved_action(engine)

    completed = await engine.execute_action("tenant-id", action.id, "obo-token")

    assert completed.status == RemediationStatus.COMPLETED
    assert completed.provider_request_id == "request-id"
    events = repo.events[action.id]
    assert [event.event_type for event in events] == [
        RemediationAuditEventType.REQUESTED,
        RemediationAuditEventType.APPROVED,
        RemediationAuditEventType.EXECUTION_STARTED,
        RemediationAuditEventType.EXECUTION_SUCCEEDED,
    ]
    assert verify_event_chain(events)


@pytest.mark.asyncio
async def test_provider_failure_is_classified_and_audited() -> None:
    repo = InMemoryRemediationRepo()
    engine = RemediationEngine(repo, ThrottledProvider())
    action = await _approved_action(engine)

    with pytest.raises(ProviderOperationError) as exc_info:
        await engine.execute_action("tenant-id", action.id, "obo-token")

    assert exc_info.value.category == ProviderFailureCategory.THROTTLED
    failed = repo.actions[action.id]
    assert failed.status == RemediationStatus.FAILED
    assert failed.failure_category == ProviderFailureCategory.THROTTLED.value
    assert failed.failure_retryable is True
    assert repo.events[action.id][-1].event_type == RemediationAuditEventType.EXECUTION_FAILED
    assert verify_event_chain(repo.events[action.id])


@pytest.mark.asyncio
async def test_missing_provider_never_records_false_success() -> None:
    repo = InMemoryRemediationRepo()
    engine = RemediationEngine(repo)
    action = await _approved_action(engine)

    with pytest.raises(ProviderOperationError) as exc_info:
        await engine.execute_action("tenant-id", action.id, "obo-token")

    assert exc_info.value.category == ProviderFailureCategory.UNSUPPORTED
    assert repo.actions[action.id].status == RemediationStatus.FAILED


@pytest.mark.asyncio
async def test_request_is_idempotent() -> None:
    repo = InMemoryRemediationRepo()
    engine = RemediationEngine(repo)

    first = await engine.request_action(
        tenant_id="tenant-id",
        project_id="project-id",
        action_type=RemediationActionType.REMOVE_ROLE,
        target_identity_id="identity-id",
        requested_by="requester@example.com",
        justification="Least privilege",
        idempotency_key="request-key",
    )
    second = await engine.request_action(
        tenant_id="tenant-id",
        project_id="project-id",
        action_type=RemediationActionType.REMOVE_ROLE,
        target_identity_id="identity-id",
        requested_by="requester@example.com",
        justification="Least privilege",
        idempotency_key="request-key",
    )

    assert second.id == first.id
    assert len(repo.actions) == 1
    assert len(repo.events[first.id]) == 1


def test_audit_chain_detects_tampering() -> None:
    event = RemediationAuditEvent(
        id="action:00000000000000000001",
        action_id="action",
        project_id="project-id",
        tenant_id="tenant-id",
        sequence=1,
        event_type=RemediationAuditEventType.REQUESTED,
        actor_id="requester@example.com",
        status=RemediationStatus.PENDING,
        occurred_at=datetime.now(UTC),
        correlation_id="correlation-id",
        details={},
        event_hash="invalid",
    )

    assert verify_event_chain([event]) is False


@pytest.mark.asyncio
async def test_request_rejects_secret_bearing_provider_payload() -> None:
    repo = InMemoryRemediationRepo()
    engine = RemediationEngine(repo)

    with pytest.raises(ValueError, match="secret-bearing"):
        await engine.request_action(
            tenant_id="tenant-id",
            project_id="project-id",
            action_type=RemediationActionType.REMOVE_ROLE,
            target_identity_id="identity-id",
            requested_by="requester@example.com",
            justification="Least privilege",
            provider_payload={"body": {"client_secret": "must-not-persist"}},
        )
