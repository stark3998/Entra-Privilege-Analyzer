"""MSAL client-credentials token acquisition for Graph API."""

from __future__ import annotations

import logging
import time
from typing import Any

import msal

logger = logging.getLogger(__name__)

_GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


def acquire_graph_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Acquire a Graph API token using client credentials flow.

    Logs timing and success/failure for debugging auth issues.
    """
    logger.info(
        "Acquiring Graph token | tenant=%s | client_id=%s",
        tenant_id, client_id[:8] + "...",
    )
    start = time.monotonic()

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result: dict[str, Any] = app.acquire_token_for_client(scopes=_GRAPH_SCOPE)
    elapsed_ms = (time.monotonic() - start) * 1000

    if "access_token" not in result:
        error = result.get("error", "unknown")
        error_desc = result.get("error_description", "No description")
        correlation_id = result.get("correlation_id", "n/a")
        logger.error(
            "Token acquisition FAILED | tenant=%s | error=%s | correlation_id=%s | elapsed=%.0fms | description=%s",
            tenant_id, error, correlation_id, elapsed_ms, error_desc[:300],
        )
        raise RuntimeError(f"Client credential token acquisition failed: {error_desc}")

    logger.info(
        "Token acquired OK | tenant=%s | elapsed=%.0fms",
        tenant_id, elapsed_ms,
    )
    return result["access_token"]
