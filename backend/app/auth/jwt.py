# backend/app/auth/jwt.py
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

_OIDC_CONFIG_URL = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
_KEY_CACHE_TTL_SECONDS = 3600  # 1 hour


class MultiTenantJwtValidator:
    """Validates Entra ID v2.0 JWTs for a multi-tenant application."""

    def __init__(self, client_id: str) -> None:
        self._client_id = client_id
        self._jwks_client: PyJWKClient | None = None
        self._jwks_uri: str | None = None
        self._last_refresh: float = 0.0

    async def _ensure_jwks_client(self) -> PyJWKClient:
        """Fetch OIDC metadata and build a JWKS client, caching for 1 hour."""
        now = time.monotonic()
        if self._jwks_client is not None and (now - self._last_refresh) < _KEY_CACHE_TTL_SECONDS:
            return self._jwks_client

        async with httpx.AsyncClient() as http:
            resp = await http.get(_OIDC_CONFIG_URL)
            resp.raise_for_status()
            oidc_config = resp.json()

        self._jwks_uri = oidc_config["jwks_uri"]
        self._jwks_client = PyJWKClient(self._jwks_uri, cache_keys=True)
        self._last_refresh = now
        logger.info("Refreshed JWKS keys from %s", self._jwks_uri)
        return self._jwks_client

    async def validate(self, token: str) -> dict[str, Any]:
        """Decode and validate a Bearer JWT.

        Returns the full token payload on success.
        Raises jwt.PyJWTError subclasses on failure.
        """
        jwks_client = await self._ensure_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # First decode without claim validation to determine the token version
        # and tenant-specific issuer expected by Entra.
        unverified = jwt.decode(token, options={"verify_signature": False})
        tid: str = unverified.get("tid", "")
        token_version = str(unverified.get("ver", "2.0"))
        expected_issuer = (
            f"https://sts.windows.net/{tid}/"
            if token_version == "1.0"
            else f"https://login.microsoftonline.com/{tid}/v2.0"
        )
        audiences = [self._client_id, f"api://{self._client_id}"]

        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audiences,
            issuer=expected_issuer,
        )
        return payload
