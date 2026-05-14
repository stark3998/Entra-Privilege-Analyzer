# backend/app/services/remediation_engine.py
"""Remediation action lifecycle: request -> approve -> execute."""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.models.remediation import (
    RemediationAction,
    RemediationActionType,
    RemediationStatus,
)
from app.services.cosmos import CosmosRepo

logger = logging.getLogger(__name__)


class RemediationEngine:
    """Manages remediation action lifecycle: request -> approve -> execute."""

    def __init__(self, repo: CosmosRepo) -> None:
        self._repo = repo

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
    ) -> RemediationAction:
        """Create a new remediation request in PENDING status."""
        now = datetime.now(UTC)
        action_id = str(uuid.uuid4())

        action = RemediationAction(
            id=action_id,
            tenant_id=tenant_id,
            project_id=project_id,
            action_type=action_type,
            target_identity_id=target_identity_id,
            target_resource_id=target_resource_id,
            target_display_name=target_display_name,
            requested_by=requested_by,
            status=RemediationStatus.PENDING,
            justification=justification,
            graph_operation=self._describe_graph_operation(action_type, target_identity_id, target_resource_id),
            created_at=now,
        )

        await self._repo.upsert_remediation_action(action)
        logger.info(
            "Remediation action requested: id=%s type=%s target=%s by=%s",
            action_id,
            action_type,
            target_identity_id,
            requested_by,
        )
        return action

    async def approve_action(
        self, tenant_id: str, action_id: str, approved_by: str,
    ) -> RemediationAction:
        """Approve a pending remediation action."""
        action = await self._repo.get_remediation_action(tenant_id, action_id)
        if action is None:
            raise ValueError(f"Remediation action {action_id} not found")
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
        logger.info(
            "Remediation action approved: id=%s by=%s", action_id, approved_by,
        )
        return action

    async def reject_action(
        self, tenant_id: str, action_id: str, rejected_by: str, reason: str,
    ) -> RemediationAction:
        """Reject a pending remediation action."""
        action = await self._repo.get_remediation_action(tenant_id, action_id)
        if action is None:
            raise ValueError(f"Remediation action {action_id} not found")
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
        logger.info(
            "Remediation action rejected: id=%s by=%s reason=%s",
            action_id,
            rejected_by,
            reason,
        )
        return action

    async def execute_action(
        self, tenant_id: str, action_id: str, obo_token: str,
    ) -> RemediationAction:
        """Execute an approved remediation action via Graph API.

        Uses OBO token for delegated permissions. The signed-in user must have
        the appropriate Entra ID admin role.

        Currently a placeholder -- logs the operation and marks completed
        without calling Graph API.
        """
        action = await self._repo.get_remediation_action(tenant_id, action_id)
        if action is None:
            raise ValueError(f"Remediation action {action_id} not found")
        if action.status != RemediationStatus.APPROVED:
            raise ValueError(
                f"Cannot execute action in '{action.status}' status; expected 'approved'"
            )

        # Transition to EXECUTING
        action = action.model_copy(update={"status": RemediationStatus.EXECUTING})
        await self._repo.upsert_remediation_action(action)

        try:
            # ---- Placeholder: actual Graph API calls go here ----
            logger.info(
                "PLACEHOLDER: would execute Graph API call for action %s: %s "
                "(token length=%d)",
                action_id,
                action.graph_operation,
                len(obo_token),
            )
            # ---- End placeholder ----

            action = action.model_copy(
                update={
                    "status": RemediationStatus.COMPLETED,
                    "completed_at": datetime.now(UTC),
                },
            )
            await self._repo.upsert_remediation_action(action)
            logger.info("Remediation action completed: id=%s", action_id)

        except Exception as exc:
            action = action.model_copy(
                update={
                    "status": RemediationStatus.FAILED,
                    "error_message": str(exc),
                    "completed_at": datetime.now(UTC),
                },
            )
            await self._repo.upsert_remediation_action(action)
            logger.error(
                "Remediation action failed: id=%s error=%s", action_id, exc,
            )

        return action

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
                f"PATCH /users/{target_identity_id} "
                f"set accountEnabled=false"
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
        }
        return descriptions.get(action_type, f"Unknown operation for {target_identity_id}")
