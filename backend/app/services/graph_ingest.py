# backend/app/services/graph_ingest.py
from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import msal

from app.config import Settings
from app.models.action import ActionEvent, ActionSource

logger = logging.getLogger(__name__)

_GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


def _deterministic_id(*parts: str) -> str:
    """Generate a deterministic UUID from the given string parts."""
    raw = "|".join(parts)
    return str(uuid.UUID(hashlib.md5(raw.encode()).hexdigest()))


class GraphIngestService:
    """Fetches audit logs, sign-in logs, and role assignments from Microsoft Graph."""

    def __init__(
        self,
        settings: Settings,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_provider: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self._settings = settings
        self._client_id = client_id or settings.azure_client_id
        self._client_secret = client_secret or settings.azure_client_secret
        self._token_provider = token_provider
        api_version = getattr(settings, "graph_api_version", "beta")
        self._graph_base = f"https://graph.microsoft.com/{api_version}"

    async def _get_client_credential_token(self, tenant_id: str) -> str:
        """Get a token for a specific tenant using client credentials flow."""
        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=self._client_secret,
        )
        result: dict[str, Any] = app.acquire_token_for_client(scopes=_GRAPH_SCOPE)
        if "access_token" not in result:
            error = result.get("error_description", "Unknown error")
            raise RuntimeError(f"Client credential token acquisition failed: {error}")
        return result["access_token"]

    async def _get_token(self, tenant_id: str) -> str:
        """Get a Graph API token — delegates to the token provider if set,
        otherwise falls back to client credentials flow."""
        if self._token_provider:
            return await self._token_provider()
        return await self._get_client_credential_token(tenant_id)

    async def _graph_get(
        self, token: str, url: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated GET to Graph API."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def _graph_get_all_pages(
        self, token: str, url: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Follow @odata.nextLink to get all pages, collecting all 'value' arrays."""
        all_items: list[dict[str, Any]] = []
        current_url: str | None = url
        current_params = params

        async with httpx.AsyncClient(timeout=30.0) as client:
            while current_url is not None:
                resp = await client.get(
                    current_url,
                    headers={"Authorization": f"Bearer {token}"},
                    params=current_params,
                )
                resp.raise_for_status()
                data = resp.json()
                all_items.extend(data.get("value", []))
                current_url = data.get("@odata.nextLink")
                current_params = None  # nextLink includes query params already

        return all_items

    async def fetch_audit_logs(
        self, tenant_id: str, delta_link: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch audit logs. Returns (events, new_delta_link).

        If delta_link is provided, fetches only new events since last sync.
        Otherwise fetches the last 30 days.
        """
        token = await self._get_token(tenant_id)

        if delta_link:
            data = await self._graph_get(token, delta_link)
            events = data.get("value", [])
            new_delta = data.get("@odata.deltaLink")
            return events, new_delta

        since = (datetime.now(UTC) - timedelta(days=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        url = f"{self._graph_base}/auditLogs/directoryAudits"
        params = {"$filter": f"activityDateTime ge {since}", "$top": "999"}
        events = await self._graph_get_all_pages(token, url, params)
        return events, None

    async def fetch_sign_in_logs(
        self, tenant_id: str, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Fetch sign-in logs for the tenant.

        Filters by createdDateTime if ``since`` is provided, otherwise last 30 days.
        """
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/auditLogs/signIns"

        cutoff = since or (datetime.now(UTC) - timedelta(days=30))
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {"$filter": f"createdDateTime ge {cutoff_str}", "$top": "999"}
        return await self._graph_get_all_pages(token, url, params)

    async def fetch_role_assignments(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch all directory role assignments with expanded principal and roleDefinition."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/roleManagement/directory/roleAssignments"
        params = {"$expand": "principal,roleDefinition"}
        return await self._graph_get_all_pages(token, url, params)

    async def fetch_role_definitions(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch all directory role definitions."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/roleManagement/directory/roleDefinitions"
        return await self._graph_get_all_pages(token, url)

    async def fetch_service_principals(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch service principals in the tenant."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/servicePrincipals"
        params = {
            "$select": (
                "id,displayName,appId,servicePrincipalType,accountEnabled,"
                "passwordCredentials,keyCredentials,createdDateTime"
            ),
        }
        return await self._graph_get_all_pages(token, url, params)

    async def fetch_users(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch users with selected fields including guest properties."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/users"
        params = {
            "$select": (
                "id,displayName,userPrincipalName,userType,accountEnabled,"
                "creationType,externalUserState,externalUserStateChangeDateTime,"
                "createdDateTime,signInActivity"
            ),
        }
        return await self._graph_get_all_pages(token, url, params)

    # ------------------------------------------------------------------
    # PIM schedule instance APIs (GA v1.0)
    # ------------------------------------------------------------------

    async def fetch_role_assignment_schedule_instances(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all active role assignments including PIM-activated ones."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/roleManagement/directory/roleAssignmentScheduleInstances"
        return await self._graph_get_all_pages(token, url)

    async def fetch_role_eligibility_schedule_instances(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all PIM-eligible role assignments."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/roleManagement/directory/roleEligibilityScheduleInstances"
        return await self._graph_get_all_pages(token, url)

    # ------------------------------------------------------------------
    # App registration & credential APIs
    # ------------------------------------------------------------------

    async def fetch_applications(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch app registrations with credential and permission details."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/applications"
        params = {
            "$select": (
                "id,appId,displayName,signInAudience,passwordCredentials,"
                "keyCredentials,requiredResourceAccess,createdDateTime,"
                "verifiedPublisher,disabledByMicrosoftStatus"
            ),
        }
        return await self._graph_get_all_pages(token, url, params)

    async def fetch_application_owners(
        self, tenant_id: str, app_object_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch owners of a specific app registration."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/applications/{app_object_id}/owners"
        params = {"$select": "id,displayName,userPrincipalName"}
        return await self._graph_get_all_pages(token, url, params)

    async def fetch_oauth2_permission_grants(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch delegated permission grants."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/oauth2PermissionGrants"
        return await self._graph_get_all_pages(token, url)

    # ------------------------------------------------------------------
    # MFA registration (bulk reporting API)
    # ------------------------------------------------------------------

    async def fetch_mfa_registration_details(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch bulk MFA registration status for all users."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/reports/authenticationMethods/userRegistrationDetails"
        return await self._graph_get_all_pages(token, url)

    # ------------------------------------------------------------------
    # Conditional Access policies
    # ------------------------------------------------------------------

    async def fetch_conditional_access_policies(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch all Conditional Access policies."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/identity/conditionalAccess/policies"
        return await self._graph_get_all_pages(token, url)

    # ------------------------------------------------------------------
    # Identity Protection
    # ------------------------------------------------------------------

    async def fetch_risky_users(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch risky users from Identity Protection. Requires P2 license."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/identityProtection/riskyUsers"
        return await self._graph_get_all_pages(token, url)

    async def fetch_risk_detections(
        self, tenant_id: str, since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch risk detections. Requires P1+ license."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/identityProtection/riskDetections"
        params: dict[str, str] | None = None
        if since:
            cutoff = since.strftime("%Y-%m-%dT%H:%M:%SZ")
            params = {"$filter": f"detectedDateTime ge {cutoff}"}
        return await self._graph_get_all_pages(token, url, params)

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    async def fetch_groups(self, tenant_id: str) -> list[dict[str, Any]]:
        """Fetch all security groups with role-assignable and dynamic metadata."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/groups"
        params = {
            "$select": (
                "id,displayName,groupTypes,securityEnabled,mailEnabled,"
                "isAssignableToRole,membershipRule,"
                "membershipRuleProcessingState,visibility,createdDateTime"
            ),
            "$filter": "securityEnabled eq true",
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "ConsistencyLevel": "eventual",
        }
        all_items: list[dict[str, Any]] = []
        current_url: str | None = url
        current_params: dict[str, str] | None = params

        async with httpx.AsyncClient(timeout=60.0) as client:
            while current_url is not None:
                resp = await client.get(
                    current_url, headers=headers, params=current_params,
                )
                resp.raise_for_status()
                data = resp.json()
                all_items.extend(data.get("value", []))
                current_url = data.get("@odata.nextLink")
                current_params = None
        return all_items

    async def fetch_group_transitive_members(
        self, tenant_id: str, group_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch transitive (nested) members of a group."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/groups/{group_id}/transitiveMembers"
        params = {"$select": "id,displayName,userPrincipalName,@odata.type"}
        return await self._graph_get_all_pages(token, url, params)

    async def fetch_group_owners(
        self, tenant_id: str, group_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch owners of a group."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/groups/{group_id}/owners"
        params = {"$select": "id,displayName,userPrincipalName"}
        return await self._graph_get_all_pages(token, url, params)

    # ------------------------------------------------------------------
    # Access Reviews
    # ------------------------------------------------------------------

    async def fetch_access_review_definitions(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch access review definitions. Requires Entra ID Governance."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/identityGovernance/accessReviews/definitions"
        return await self._graph_get_all_pages(token, url)

    # ------------------------------------------------------------------
    # Cross-tenant access
    # ------------------------------------------------------------------

    async def fetch_cross_tenant_access_partners(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch cross-tenant access policy partner configurations."""
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/policies/crossTenantAccessPolicy/partners"
        return await self._graph_get_all_pages(token, url)

    # ------------------------------------------------------------------
    # Beta-only: Service Principal & App Credential sign-in reports
    # ------------------------------------------------------------------

    async def fetch_service_principal_sign_in_activities(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch last sign-in activity for service principals (beta only).

        Returns empty list if the endpoint is unavailable (e.g., using v1.0).
        """
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/reports/servicePrincipalSignInActivities"
        try:
            return await self._graph_get_all_pages(token, url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 404):
                logger.debug("servicePrincipalSignInActivities not available (version=%s)", self._settings.graph_api_version)
                return []
            raise

    async def fetch_app_credential_sign_in_activities(
        self, tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch last sign-in activity per app credential (beta only).

        Returns empty list if the endpoint is unavailable (e.g., using v1.0).
        """
        token = await self._get_token(tenant_id)
        url = f"{self._graph_base}/reports/appCredentialSignInActivities"
        try:
            return await self._graph_get_all_pages(token, url)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 404):
                logger.debug("appCredentialSignInActivities not available (version=%s)", self._settings.graph_api_version)
                return []
            raise

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_audit_event(
        tenant_id: str, raw: dict[str, Any]
    ) -> tuple[ActionEvent, str, str]:
        """Parse a raw audit log entry into an ActionEvent.

        Returns (event, actor_object_id, actor_display_name).
        Extracts the actor from ``initiatedBy.user`` or ``initiatedBy.app``.
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

        event_id = _deterministic_id(
            tenant_id,
            raw.get("id", ""),
            "audit",
        )

        timestamp_str = raw.get("activityDateTime", "")
        timestamp = (
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if timestamp_str
            else datetime.now(UTC)
        )

        # Determine identity type prefix for the identity_id
        identity_prefix = "ServicePrincipal" if app_info.get("id") else "User"
        identity_id = f"{identity_prefix}_{actor_id}"

        event = ActionEvent(
            id=event_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            identity_display_name=actor_name,
            action=raw.get("activityDisplayName", "Unknown"),
            resource=first_target.get("displayName"),
            resource_type=first_target.get("type"),
            result=raw.get("result", "success"),
            source=ActionSource.AUDIT_LOG,
            correlation_id=raw.get("correlationId"),
            ip_address=None,
            timestamp=timestamp,
            raw_data=raw,
        )
        return event, actor_id, actor_name

    @staticmethod
    def parse_sign_in_event(
        tenant_id: str, raw: dict[str, Any]
    ) -> tuple[ActionEvent, str, str]:
        """Parse a raw sign-in log entry into an ActionEvent.

        Returns (event, actor_object_id, actor_display_name).
        """
        actor_id = raw.get("userId", "unknown")
        actor_name = raw.get("userDisplayName", "Unknown")

        # If userId is empty, it might be a service principal sign-in
        if not actor_id or actor_id == "00000000-0000-0000-0000-000000000000":
            actor_id = raw.get("appId", "unknown")
            actor_name = raw.get("appDisplayName", actor_name)
            identity_prefix = "ServicePrincipal"
        else:
            identity_prefix = "User"

        identity_id = f"{identity_prefix}_{actor_id}"

        event_id = _deterministic_id(
            tenant_id,
            raw.get("id", ""),
            "signin",
        )

        timestamp_str = raw.get("createdDateTime", "")
        timestamp = (
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if timestamp_str
            else datetime.now(UTC)
        )

        status_info = raw.get("status", {})
        result = "success" if status_info.get("errorCode", 0) == 0 else "failure"

        event = ActionEvent(
            id=event_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            identity_display_name=actor_name,
            action="Sign-in",
            resource=raw.get("resourceDisplayName"),
            resource_type="Application",
            result=result,
            source=ActionSource.SIGN_IN_LOG,
            correlation_id=raw.get("correlationId"),
            ip_address=raw.get("ipAddress"),
            timestamp=timestamp,
            raw_data=raw,
        )
        return event, actor_id, actor_name
