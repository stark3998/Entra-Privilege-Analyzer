from __future__ import annotations

import logging
from typing import Any

import jwt
import msal

logger = logging.getLogger(__name__)

_GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

REQUIRED_PERMISSIONS: list[str] = [
    "AuditLog.Read.All",
    "Directory.Read.All",
    "User.Read.All",
    "Application.Read.All",
    "RoleManagement.Read.Directory",
    "RoleManagement.Read.All",
    "Policy.Read.All",
    "GroupMember.Read.All",
]

OPTIONAL_PERMISSIONS: list[str] = [
    "IdentityRiskEvent.Read.All",
    "IdentityRiskyServicePrincipal.Read.All",
    "AccessReview.Read.All",
]


class PermissionValidator:
    """Validates that an app registration has sufficient Graph API permissions."""

    async def validate(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Acquire a client credential token and inspect its roles claim.

        Returns {"valid": bool, "granted": [...], "missing": [...]}.
        """
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        result: dict[str, Any] = app.acquire_token_for_client(scopes=_GRAPH_SCOPE)

        if "access_token" not in result:
            error = result.get("error_description", "Token acquisition failed")
            logger.warning(
                "Permission validation failed for tenant %s: %s",
                tenant_id,
                error,
            )
            return {
                "valid": False,
                "granted": [],
                "missing": REQUIRED_PERMISSIONS,
                "error": error,
            }

        token = result["access_token"]
        payload = jwt.decode(token, options={"verify_signature": False})
        granted_roles: list[str] = payload.get("roles", [])

        missing = [p for p in REQUIRED_PERMISSIONS if p not in granted_roles]
        return {
            "valid": len(missing) == 0,
            "granted": [p for p in REQUIRED_PERMISSIONS if p in granted_roles],
            "missing": missing,
        }
