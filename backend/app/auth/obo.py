# backend/app/auth/obo.py
from __future__ import annotations

import logging
from typing import Any

import msal

from app.config import Settings

logger = logging.getLogger(__name__)

_GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


class OboTokenProvider:
    """Exchanges a user assertion for a Graph API token via the OBO flow."""

    def __init__(self, settings: Settings) -> None:
        self._app: msal.ConfidentialClientApplication = msal.ConfidentialClientApplication(
            settings.azure_client_id,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
            client_credential=settings.azure_client_secret,
        )

    async def get_graph_token(self, user_assertion: str) -> str:
        """Exchange a user token for a Microsoft Graph token.

        Args:
            user_assertion: The Bearer token from the incoming request.

        Returns:
            An access token scoped to Microsoft Graph.

        Raises:
            RuntimeError: If the OBO exchange fails.
        """
        result: dict[str, Any] = self._app.acquire_token_on_behalf_of(
            user_assertion=user_assertion,
            scopes=_GRAPH_SCOPES,
        )
        if "access_token" not in result:
            error_desc = result.get("error_description", "Unknown OBO error")
            logger.error("OBO token exchange failed: %s", error_desc)
            raise RuntimeError(f"OBO token exchange failed: {error_desc}")

        return result["access_token"]
