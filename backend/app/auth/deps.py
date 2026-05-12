# backend/app/auth/deps.py
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.jwt import MultiTenantJwtValidator
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_validator: MultiTenantJwtValidator | None = None


class CurrentUser(BaseModel):
    """Authenticated user extracted from the JWT."""

    oid: str  # user object ID
    tid: str  # tenant ID
    name: str
    email: str
    roles: list[str]  # app roles from the token


_MOCK_USER = CurrentUser(
    oid="local-dev-user",
    tid="local-dev-tenant",
    name="Dev User",
    email="dev@localhost",
    roles=["SecurityEngineer", "IAMAdmin", "Executive"],
)


def _get_validator(settings: Settings) -> MultiTenantJwtValidator:
    """Return a singleton JWT validator."""
    global _validator
    if _validator is None:
        _validator = MultiTenantJwtValidator(client_id=settings.azure_client_id)
    return _validator


async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """FastAPI dependency that extracts the authenticated user.

    In LOCAL_MODE, returns a mock user without any token validation.
    Otherwise, validates the Bearer JWT against Entra ID.
    """
    if settings.local_mode:
        return _MOCK_USER

    auth_header: str | None = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header.removeprefix("Bearer ")
    validator = _get_validator(settings)

    try:
        payload: dict[str, Any] = await validator.validate(token)
    except Exception as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    return CurrentUser(
        oid=payload.get("oid", ""),
        tid=payload.get("tid", ""),
        name=payload.get("name", ""),
        email=payload.get("preferred_username", ""),
        roles=payload.get("roles", []),
    )


def validate_tenant_access(
    tenant_id: str,
    user: CurrentUser,
    settings: Settings | None = None,
) -> None:
    """Raise 403 if the user's tenant does not match the path tenant_id.

    In LOCAL_MODE the check is skipped so tests work with any tenant ID.
    Accepts an optional ``settings`` parameter so callers can pass the
    DI-provided instance; falls back to ``get_settings()`` when not given.
    """
    resolved = settings if settings is not None else get_settings()
    if resolved.local_mode:
        return
    if user.tid != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access denied",
        )


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """Dependency factory that checks the user has at least one of the specified roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("IAMAdmin"))])
    """

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in user.roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return user

    return _check
