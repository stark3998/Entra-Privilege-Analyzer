# backend/app/auth/obo.py
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import msal

from app.config import Settings

logger = logging.getLogger(__name__)

_GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


class OboTokenProvider:
    """Exchanges a user assertion for a Graph API token via the OBO flow."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build_app(self, tenant_id: str | None = None) -> msal.ConfidentialClientApplication:
        authority_tid = tenant_id or self._settings.azure_tenant_id
        return msal.ConfidentialClientApplication(
            self._settings.azure_client_id,
            authority=f"https://login.microsoftonline.com/{authority_tid}",
            client_credential=self._settings.azure_client_secret,
        )

    async def get_graph_token(
        self,
        user_assertion: str,
        tenant_id: str | None = None,
    ) -> str:
        """Exchange a user token for a Microsoft Graph token.

        Args:
            user_assertion: The Bearer token from the incoming request.
            tenant_id: Target tenant for cross-tenant OBO. Defaults to the
                app's home tenant.

        Returns:
            An access token scoped to Microsoft Graph.

        Raises:
            RuntimeError: If the OBO exchange fails.
        """
        app = self._build_app(tenant_id)
        result: dict[str, Any] = app.acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=_GRAPH_SCOPES,
        )
        if "access_token" not in result:
            error_desc = result.get("error_description", "Unknown OBO error")
            logger.error("OBO token exchange failed: %s", error_desc)
            raise RuntimeError(f"OBO token exchange failed: {error_desc}")

        return result["access_token"]

    def get_token_provider(
        self,
        user_assertion: str,
        tenant_id: str | None = None,
    ) -> Callable[[], Awaitable[str]]:
        """Return an async callable that produces a fresh Graph token on each call.

        MSAL caches tokens internally, so repeated calls are cheap. This is
        useful for long-running scans where the token may expire mid-flight.
        """

        async def _provider() -> str:
            return await self.get_graph_token(user_assertion, tenant_id)

        return _provider
