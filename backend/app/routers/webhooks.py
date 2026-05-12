# backend/app/routers/webhooks.py
"""API endpoints for Microsoft Graph webhook notifications and subscriptions."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.webhook import WebhookHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


# ------------------------------------------------------------------
# Graph change notification endpoint (public — Graph calls this)
# ------------------------------------------------------------------


@router.post("/api/webhooks/graph")
async def graph_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    validationToken: str | None = Query(default=None),
    repo: CosmosRepo = Depends(get_cosmos_repo),
) -> Any:
    """Handle incoming Graph change notifications.

    - Subscription validation: returns validationToken as text/plain.
    - Actual notifications: processes in background.
    """
    handler = WebhookHandler(repo)

    # Subscription validation handshake
    if validationToken is not None:
        try:
            token = handler.validate_subscription(validationToken)
        except ValueError:
            return PlainTextResponse(content="", status_code=status.HTTP_400_BAD_REQUEST)
        return PlainTextResponse(content=token, status_code=status.HTTP_200_OK)

    # Parse notification payload
    body = await request.json()
    notifications = body.get("value", [])

    queued = 0
    for notification in notifications:
        tenant_id = notification.get("tenantId", "")
        if tenant_id and handler.validate_tenant_id(tenant_id):
            background_tasks.add_task(
                handler.process_notification, tenant_id, notification,
            )
            queued += 1

    return {"status": "accepted", "notifications_queued": queued}


# ------------------------------------------------------------------
# Subscription management endpoints (authenticated)
# ------------------------------------------------------------------


@router.post(
    "/api/tenants/{tenant_id}/subscriptions/create",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_subscription(
    tenant_id: str,
    request: Request,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Create a new Graph API change notification subscription."""
    validate_tenant_access(tenant_id, user, settings)

    body = await request.json()
    resource = body.get("resource", "")
    notification_url = body.get("notification_url", "")

    logger.info(
        "audit.subscription.create tenant=%s resource=%s user=%s",
        tenant_id,
        resource,
        user.oid,
    )

    handler = WebhookHandler(repo)
    subscription = await handler.create_subscription(
        tenant_id, resource, notification_url,
    )
    return {"status": "accepted", "subscription": subscription}


@router.get("/api/tenants/{tenant_id}/subscriptions")
async def list_subscriptions(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List active Graph API subscriptions for a tenant."""
    validate_tenant_access(tenant_id, user, settings)

    handler = WebhookHandler(repo)
    subscriptions = await handler.list_subscriptions(tenant_id)
    return {
        "tenant_id": tenant_id,
        "subscriptions": subscriptions,
        "count": len(subscriptions),
    }
