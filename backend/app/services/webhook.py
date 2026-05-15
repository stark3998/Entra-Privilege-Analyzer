# backend/app/services/webhook.py
"""Microsoft Graph change notification webhook handler."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.services.cosmos import CosmosRepo

logger = logging.getLogger(__name__)

_VALIDATION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.]{1,512}$")
_TENANT_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class WebhookHandler:
    """Processes incoming Graph API change notifications."""

    def __init__(self, repo: CosmosRepo, expected_client_state: str = "") -> None:
        self._repo = repo
        self._expected_client_state = expected_client_state

    def validate_subscription(self, validation_token: str) -> str:
        """Return the validation token for Graph subscription validation handshake.

        Validates the token format to prevent reflected content injection.
        """
        if not _VALIDATION_TOKEN_PATTERN.match(validation_token):
            raise ValueError("Invalid validation token format")
        return validation_token

    @staticmethod
    def validate_tenant_id(tenant_id: str) -> bool:
        """Check that tenant_id looks like a valid GUID."""
        return bool(_TENANT_ID_PATTERN.match(tenant_id))

    async def process_notification(
        self,
        tenant_id: str,
        notification: dict[str, Any],
    ) -> None:
        """Extract change data from a Graph notification and log for processing."""
        if self._expected_client_state:
            received_state = notification.get("clientState", "")
            if received_state != self._expected_client_state:
                logger.warning("webhook.invalid_client_state tenant=%s", tenant_id)
                return

        if not self.validate_tenant_id(tenant_id):
            logger.warning("webhook.invalid_tenant_id value=%s", tenant_id[:50])
            return

        resource = notification.get("resource", "unknown")
        change_type = notification.get("changeType", "unknown")

        logger.info(
            "webhook.notification tenant=%s resource=%s change=%s",
            tenant_id,
            resource,
            change_type,
        )

        await self._repo.upsert_sync_state(
            tenant_id,
            "webhook_last_notification",
            {
                "resource": resource,
                "change_type": change_type,
                "received_at": datetime.now(UTC).isoformat(),
            },
        )

    async def create_subscription(
        self,
        tenant_id: str,
        resource: str,
        notification_url: str,
    ) -> dict[str, Any]:
        """Create a Graph API subscription (stub)."""
        subscription_id = f"sub_{tenant_id}_{resource.replace('/', '_')}"
        subscription = {
            "id": subscription_id,
            "tenant_id": tenant_id,
            "resource": resource,
            "notification_url": notification_url,
            "change_type": "created,updated,deleted",
            "expiration_datetime": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
        }

        logger.info(
            "webhook.subscription.created tenant=%s resource=%s",
            tenant_id,
            resource,
        )

        await self._repo.upsert_sync_state(
            tenant_id,
            f"subscription_{subscription_id}",
            subscription,
        )
        return subscription

    async def list_subscriptions(self, tenant_id: str) -> list[dict[str, Any]]:
        """List active subscriptions for a tenant."""
        return await self._repo.list_sync_states_by_prefix(tenant_id, "subscription_")
