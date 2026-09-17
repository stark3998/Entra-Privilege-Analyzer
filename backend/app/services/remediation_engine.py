# backend/app/services/remediation_engine.py
"""Remediation action lifecycle: request -> approve -> execute."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.remediation import (
    RemediationAction,
    RemediationActionType,
    RemediationAuditEventType,
    RemediationStatus,
)
from app.services.provider_errors import (
    ProviderFailureCategory,
    ProviderOperationError,
)
from app.services.remediation_audit import RemediationAuditTrail
from app.services.remediation_provider import RemediationProvider

logger = logging.getLogger(__name__)
_FORBIDDEN_PROVIDER_FIELDS = {
    "access_token",
    "client_secret",
    "connection_string",
    "cosmos_key",
    "encryption_key",
    "password",
}


class RemediationEngine:
    """Manages remediation action lifecycle: request -> approve -> execute."""

    def __init__(
        self,
        repo: Any,
        provider: RemediationProvider | None = None,
    ) -> None:
        self._repo = repo
        self._provider = provider
        self._audit = RemediationAuditTrail(repo)

    async def request_action(
        self,
        tenant_id: str,
        project_id: str,
        action_type: RemediationActionType,
        target_identity_id: str,
        requested_by: str,
        justification: str,
        target_resource_id: str | None = None,
        target_display_name: str = "",
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
        provider: str = "microsoft_graph",
        provider_payload: dict[str, Any] | None = None,
        preconditions: list[dict[str, Any]] | None = None,
        postconditions: list[dict[str, Any]] | None = None,
        compensation: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> RemediationAction:
        """Create a new remediation request in PENDING status."""
        forbidden = _find_forbidden_fields(provider_payload or {})
        if forbidden:
            raise ValueError(
                "Provider payload contains secret-bearing fields: "
                + ", ".join(sorted(forbidden))
            )
        if idempotency_key:
            existing = await self._repo.get_remediation_action_by_idempotency_key(
                idempotency_key
            )
            if existing is not None:
                if (
                    existing.tenant_id != tenant_id
                    or existing.project_id != project_id
                    or existing.action_type != action_type
                    or existing.target_identity_id != target_identity_id
                    or existing.target_resource_id != target_resource_id
                    or existing.provider != provider
                    or existing.provider_payload != (provider_payload or {})
                    or existing.dry_run != dry_run
                ):
                    raise ValueError(
                        "Idempotency key is already used by a different remediation request"
                    )
                return existing

        now = datetime.now(UTC)
        action_id = str(uuid.uuid4())

        action = RemediationAction(
            id=action_id,
            tenant_id=tenant_id,
            project_id=project_id,
            correlation_id=correlation_id or str(uuid.uuid4()),
            idempotency_key=idempotency_key or action_id,
            action_type=action_type,
            target_identity_id=target_identity_id,
            target_resource_id=target_resource_id,
            target_display_name=target_display_name,
            requested_by=requested_by,
            status=RemediationStatus.PENDING,
            justification=justification,
            graph_operation=self._describe_graph_operation(
                action_type, target_identity_id, target_resource_id
            ),
            provider=provider,
            provider_payload=provider_payload or {},
            preconditions=preconditions or [],
            postconditions=postconditions or [],
            compensation=compensation,
            dry_run=dry_run,
            created_at=now,
        )

        await self._repo.upsert_remediation_action(action)
        await self._audit.append(
            action,
            RemediationAuditEventType.REQUESTED,
            requested_by,
            RemediationStatus.PENDING,
            {
                "action_type": action.action_type.value,
                "target_identity_id": target_identity_id,
                "target_resource_id": target_resource_id,
                "justification": justification,
            },
        )
        logger.info(
            "Remediation action requested: id=%s correlation_id=%s type=%s target=%s by=%s",
            action_id,
            action.correlation_id,
            action_type,
            target_identity_id,
            requested_by,
        )
        return action

    async def approve_action(
        self,
        tenant_id: str,
        action_id: str,
        approved_by: str,
    ) -> RemediationAction:
        """Approve a pending remediation action."""
        action = await self._get_action(tenant_id, action_id)
        if action.status != RemediationStatus.PENDING:
            raise ValueError(
                f"Cannot approve action in '{action.status}' status; expected 'pending'"
            )

        action = action.model_copy(
            update={
                "status": RemediationStatus.APPROVED,
                "approved_by": approved_by,
                "approved_at": datetime.now(UTC),
            },
        )
        await self._repo.upsert_remediation_action(action)
        await self._audit.append(
            action,
            RemediationAuditEventType.APPROVED,
            approved_by,
            RemediationStatus.APPROVED,
        )
        logger.info(
            "Remediation action approved: id=%s by=%s",
            action_id,
            approved_by,
        )
        return action

    async def reject_action(
        self,
        tenant_id: str,
        action_id: str,
        rejected_by: str,
        reason: str,
    ) -> RemediationAction:
        """Reject a pending remediation action."""
        action = await self._get_action(tenant_id, action_id)
        if action.status != RemediationStatus.PENDING:
            raise ValueError(
                f"Cannot reject action in '{action.status}' status; expected 'pending'"
            )

        action = action.model_copy(
            update={
                "status": RemediationStatus.REJECTED,
                "approved_by": rejected_by,
                "error_message": reason,
                "completed_at": datetime.now(UTC),
            },
        )
        await self._repo.upsert_remediation_action(action)
        await self._audit.append(
            action,
            RemediationAuditEventType.REJECTED,
            rejected_by,
            RemediationStatus.REJECTED,
            {"reason": reason},
        )
        logger.info(
            "Remediation action rejected: id=%s by=%s reason=%s",
            action_id,
            rejected_by,
            reason,
        )
        return action

    async def execute_action(
        self,
        tenant_id: str,
        action_id: str,
        obo_token: str,
    ) -> RemediationAction:
        """Execute an approved action through an injected deterministic provider."""
        action = await self._get_action(tenant_id, action_id)
        if action.status != RemediationStatus.APPROVED:
            raise ValueError(
                f"Cannot execute action in '{action.status}' status; expected 'approved'"
            )

        action = action.model_copy(update={"status": RemediationStatus.EXECUTING})
        await self._repo.upsert_remediation_action(action)
        await self._audit.append(
            action,
            RemediationAuditEventType.EXECUTION_STARTED,
            "system",
            RemediationStatus.EXECUTING,
            {"operation": action.graph_operation},
        )

        try:
            if self._provider is None:
                raise ProviderOperationError(
                    ProviderFailureCategory.UNSUPPORTED,
                    "No remediation provider is configured for this action",
                    provider="unconfigured",
                    retryable=False,
                )

            result = await self._provider.execute(action, obo_token)
            action = action.model_copy(
                update={
                    "status": RemediationStatus.COMPLETED,
                    "completed_at": datetime.now(UTC),
                    "provider_operation_id": result.operation_id,
                    "provider_request_id": result.request_id,
                    "error_message": None,
                    "failure_category": None,
                    "failure_retryable": False,
                },
            )
            await self._repo.upsert_remediation_action(action)
            await self._audit.append(
                action,
                RemediationAuditEventType.EXECUTION_SUCCEEDED,
                "system",
                RemediationStatus.COMPLETED,
                {
                    "provider": result.provider,
                    "operation_id": result.operation_id,
                    "request_id": result.request_id,
                    "result": result.details,
                },
            )
            logger.info(
                "Remediation action completed: id=%s correlation_id=%s provider=%s",
                action_id,
                action.correlation_id,
                result.provider,
            )
            return action
        except ProviderOperationError as exc:
            action = action.model_copy(
                update={
                    "status": RemediationStatus.FAILED,
                    "error_message": str(exc),
                    "provider_request_id": exc.request_id,
                    "failure_category": exc.category.value,
                    "failure_retryable": exc.retryable,
                    "completed_at": datetime.now(UTC),
                },
            )
            await self._repo.upsert_remediation_action(action)
            await self._audit.append(
                action,
                RemediationAuditEventType.EXECUTION_FAILED,
                "system",
                RemediationStatus.FAILED,
                {
                    "provider": exc.provider,
                    "category": exc.category.value,
                    "retryable": exc.retryable,
                    "status_code": exc.status_code,
                    "error_code": exc.error_code,
                    "request_id": exc.request_id,
                    "message": str(exc),
                },
            )
            logger.error(
                "Remediation action failed: id=%s correlation_id=%s category=%s retryable=%s",
                action_id,
                action.correlation_id,
                exc.category,
                exc.retryable,
            )
            raise
        except Exception as exc:
            action = action.model_copy(
                update={
                    "status": RemediationStatus.FAILED,
                    "error_message": "Unexpected remediation provider failure",
                    "failure_category": ProviderFailureCategory.UNKNOWN.value,
                    "failure_retryable": False,
                    "completed_at": datetime.now(UTC),
                },
            )
            await self._repo.upsert_remediation_action(action)
            await self._audit.append(
                action,
                RemediationAuditEventType.EXECUTION_FAILED,
                "system",
                RemediationStatus.FAILED,
                {
                    "provider": "unknown",
                    "category": ProviderFailureCategory.UNKNOWN.value,
                    "retryable": False,
                },
            )
            logger.exception(
                "Unexpected remediation provider failure: id=%s correlation_id=%s",
                action_id,
                action.correlation_id,
            )
            raise RuntimeError("Unexpected remediation provider failure") from exc

    async def _get_action(
        self,
        tenant_id: str,
        action_id: str,
    ) -> RemediationAction:
        action = await self._repo.get_remediation_action(action_id)
        if action is None:
            raise ValueError(f"Remediation action {action_id} not found")
        if action.tenant_id != tenant_id:
            raise ValueError(f"Remediation action {action_id} does not belong to this tenant")
        return action

    async def get_action(
        self,
        tenant_id: str,
        action_id: str,
    ) -> RemediationAction:
        return await self._get_action(tenant_id, action_id)

    @staticmethod
    def _describe_graph_operation(
        action_type: RemediationActionType,
        target_identity_id: str,
        target_resource_id: str | None,
    ) -> str:
        """Return human-readable description of the Graph API call."""
        descriptions: dict[RemediationActionType, str] = {
            RemediationActionType.REMOVE_ROLE: (
                f"DELETE /roleManagement/directory/roleAssignments "
                f"for identity {target_identity_id}"
            ),
            RemediationActionType.CREATE_PIM_ELIGIBLE: (
                f"POST /roleManagement/directory/roleEligibilityScheduleRequests "
                f"for identity {target_identity_id}"
            ),
            RemediationActionType.DISABLE_ACCOUNT: (
                f"PATCH /users/{target_identity_id} set accountEnabled=false"
            ),
            RemediationActionType.REMOVE_GROUP_MEMBER: (
                f"DELETE /groups/{target_resource_id}/members/{target_identity_id}/$ref"
            ),
            RemediationActionType.REVOKE_CONSENT: (
                f"DELETE /servicePrincipals/{target_identity_id}/oauth2PermissionGrants"
            ),
            RemediationActionType.REMOVE_APP_CREDENTIAL: (
                f"POST /applications/{target_resource_id}/removePassword "
                f"for identity {target_identity_id}"
            ),
            RemediationActionType.CONVERT_PERMANENT_TO_PIM: (
                f"DELETE permanent assignment then POST eligibility schedule "
                f"for identity {target_identity_id}"
            ),
            RemediationActionType.CREATE_CUSTOM_ROLE: "POST custom role definition",
            RemediationActionType.UPDATE_CUSTOM_ROLE: (
                f"PATCH custom role definition {target_resource_id}"
            ),
            RemediationActionType.DELETE_CUSTOM_ROLE: (
                f"DELETE custom role definition {target_resource_id}"
            ),
            RemediationActionType.ASSIGN_ENTRA_ROLE: (
                f"POST Entra role assignment for identity {target_identity_id}"
            ),
            RemediationActionType.ASSIGN_AZURE_ROLE: (
                f"PUT Azure role assignment for identity {target_identity_id}"
            ),
            RemediationActionType.REMOVE_AZURE_ROLE: (
                f"DELETE Azure role assignment {target_resource_id}"
            ),
            RemediationActionType.CREATE_PIM_AZURE_ELIGIBLE: (
                f"PUT Azure PIM eligible assignment for identity {target_identity_id}"
            ),
            RemediationActionType.ADD_GROUP_MEMBER: (
                f"POST /groups/{target_resource_id}/members/$ref "
                f"for identity {target_identity_id}"
            ),
            RemediationActionType.GRANT_APP_PERMISSION: (
                f"POST application grant for identity {target_identity_id}"
            ),
            RemediationActionType.ADD_FEDERATED_CREDENTIAL: (
                f"POST federated credential for application {target_resource_id}"
            ),
            RemediationActionType.ENABLE_ACCOUNT: (
                f"PATCH /users/{target_identity_id} set accountEnabled=true"
            ),
        }
        return descriptions.get(action_type, f"Unknown operation for {target_identity_id}")


def _find_forbidden_fields(value: Any) -> set[str]:
    if isinstance(value, dict):
        found = {
            str(key).lower()
            for key in value
            if str(key).lower() in _FORBIDDEN_PROVIDER_FIELDS
        }
        for child in value.values():
            found.update(_find_forbidden_fields(child))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for child in value:
            found.update(_find_forbidden_fields(child))
        return found
    return set()
