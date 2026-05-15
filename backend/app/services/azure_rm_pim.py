from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
import msal

from app.config import Settings

logger = logging.getLogger(__name__)

_ARM_SCOPE = ["https://management.azure.com/.default"]
_ARM_BASE = "https://management.azure.com"
_API_VERSION = "2020-10-01"


class AzureRmPimService:
    """Fetches Azure RBAC PIM activation requests from the Azure Resource Manager API."""

    def __init__(
        self,
        settings: Settings,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self._settings = settings
        self._client_id = client_id or settings.azure_client_id
        self._client_secret = client_secret or settings.azure_client_secret

    async def _get_arm_token(self, tenant_id: str) -> str:
        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=self._client_secret,
        )
        result = app.acquire_token_for_client(scopes=_ARM_SCOPE)
        if "access_token" not in result:
            raise RuntimeError(
                f"ARM token acquisition failed: {result.get('error_description', 'unknown error')}"
            )
        return result["access_token"]

    async def _arm_get_all_pages(
        self,
        token: str,
        url: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {token}"}
        results: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            next_url: str | None = url
            while next_url:
                resp = await client.get(next_url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                results.extend(data.get("value", []))
                next_url = data.get("nextLink")
                params = None
        return results

    async def fetch_rbac_assignment_schedule_requests(
        self,
        tenant_id: str,
        subscription_id: str,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch Azure RBAC PIM activation requests for a subscription."""
        token = await self._get_arm_token(tenant_id)
        scope = f"/subscriptions/{subscription_id}"
        url = f"{_ARM_BASE}{scope}/providers/Microsoft.Authorization/roleAssignmentScheduleRequests"
        params: dict[str, str] = {"api-version": _API_VERSION}

        filter_parts = ["requestType eq 'SelfActivate'"]
        if since:
            filter_parts.append(f"createdOn ge {since.isoformat()}")
        params["$filter"] = " and ".join(filter_parts)

        try:
            return await self._arm_get_all_pages(token, url, params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                logger.warning(
                    "Azure RBAC PIM unavailable for subscription %s: %s",
                    subscription_id,
                    exc.response.status_code,
                )
                return []
            raise

    async def fetch_rbac_role_definitions(
        self,
        tenant_id: str,
        subscription_id: str,
    ) -> dict[str, str]:
        """Fetch Azure RBAC role definitions and return id->displayName map."""
        token = await self._get_arm_token(tenant_id)
        scope = f"/subscriptions/{subscription_id}"
        url = f"{_ARM_BASE}{scope}/providers/Microsoft.Authorization/roleDefinitions"
        params = {"api-version": _API_VERSION}

        try:
            definitions = await self._arm_get_all_pages(token, url, params)
        except httpx.HTTPStatusError:
            logger.warning("Could not fetch RBAC role definitions for %s", subscription_id)
            return {}

        lookup: dict[str, str] = {}
        for defn in definitions:
            props = defn.get("properties", {})
            role_id = defn.get("name", defn.get("id", ""))
            lookup[role_id] = props.get("roleName", "Unknown Role")
            full_id = defn.get("id", "")
            if full_id:
                lookup[full_id] = props.get("roleName", "Unknown Role")
        return lookup
