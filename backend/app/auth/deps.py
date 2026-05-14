# backend/app/auth/deps.py
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.auth.jwt import MultiTenantJwtValidator
from app.config import Settings, get_settings
from app.models.project import Project

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


_ROLE_HIERARCHY: dict[str, int] = {"viewer": 0, "operator": 1, "admin": 2}

_MOCK_PROJECT = Project(
    id="local-dev-project",
    owner_id="local-dev-user",
    name="Local Dev Project",
    target_tenant_id="local-dev-tenant",
    target_tenant_name="Local Dev Tenant",
    client_id="local-dev-client",
    encrypted_client_secret="",
    status="active",
    created_at=datetime(2024, 1, 1),
    updated_at=datetime(2024, 1, 1),
)


async def validate_project_access(
    project_id: str,
    user: CurrentUser,
    repo: Any,
    settings: Settings | None = None,
    required_role: str | None = None,
) -> Project:
    """Validate user has access to a project and return the project.

    Owner is implicitly an admin. Otherwise checks project_members.
    """
    resolved = settings if settings is not None else get_settings()
    if resolved.local_mode:
        return _MOCK_PROJECT

    project = await repo.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if project.owner_id == user.oid:
        return project

    member = await repo.get_project_member(project_id, user.oid)
    if member is None:
        member = await repo.get_project_member_by_email(project_id, user.email)
        if member is not None:
            member.user_id = user.oid
            await repo.upsert_project_member(member)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this project",
            )

    if required_role is not None:
        user_level = _ROLE_HIERARCHY.get(member.role, -1)
        required_level = _ROLE_HIERARCHY.get(required_role, 999)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires project role: {required_role}",
            )

    return project


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
