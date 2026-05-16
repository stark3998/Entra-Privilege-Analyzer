from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.auth.deps import (
    CurrentUser,
    get_current_user,
    validate_project_access,
)
from app.config import Settings, get_settings
from app.models.project import Project, ProjectMember
from app.services.master_repo import MasterRepo, get_master_repo
from app.services.crypto import CryptoService
from app.services.permission_validator import PermissionValidator
from app.services.project_db_manager import ProjectDatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ------------------------------------------------------------------
# Request / response schemas
# ------------------------------------------------------------------


class CreateProjectPayload(BaseModel):
    name: str
    target_tenant_id: str
    target_tenant_name: str
    client_id: str = ""
    client_secret: str = ""


class UpdateProjectPayload(BaseModel):
    name: str | None = None
    sync_schedule_hours: int | None = None
    baseline_window_days: int | None = None


class UpdateCredentialsPayload(BaseModel):
    client_id: str
    client_secret: str


class InviteMemberPayload(BaseModel):
    email: str
    role: str = "viewer"


class UpdateMemberPayload(BaseModel):
    role: str


class ProjectResponse(BaseModel):
    """Project data returned to the client — never includes decrypted secret."""

    id: str
    owner_id: str
    owner_email: str
    name: str
    target_tenant_id: str
    target_tenant_name: str
    client_id: str
    status: str
    permission_status: dict[str, Any] | None
    last_scan_at: datetime | None
    last_scan_status: str | None
    identity_count: int
    risk_score: float
    sync_schedule_hours: int
    baseline_window_days: int
    created_at: datetime
    updated_at: datetime


def _project_response(p: Project) -> dict[str, Any]:
    return ProjectResponse(
        id=p.id,
        owner_id=p.owner_id,
        owner_email=p.owner_email,
        name=p.name,
        target_tenant_id=p.target_tenant_id,
        target_tenant_name=p.target_tenant_name,
        client_id=p.client_id,
        status=p.status,
        permission_status=p.permission_status,
        last_scan_at=p.last_scan_at,
        last_scan_status=p.last_scan_status,
        identity_count=p.identity_count,
        risk_score=p.risk_score,
        sync_schedule_hours=p.sync_schedule_hours,
        baseline_window_days=p.baseline_window_days,
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump(mode="json")


# ------------------------------------------------------------------
# Project CRUD
# ------------------------------------------------------------------


@router.get("/me")
async def whoami(
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the authenticated user's claims."""
    return {
        "oid": user.oid,
        "tid": user.tid,
        "tenant_id": user.tid,
        "name": user.name,
        "email": user.email,
        "roles": user.roles,
    }


@router.get("")
async def list_projects(
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
) -> list[dict[str, Any]]:
    """List all projects the user owns or is a member of."""
    projects = await repo.list_projects_for_user(user.oid, user.email)
    return [_project_response(p) for p in projects]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: CreateProjectPayload,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Create a new project. Validates Graph API permissions when credentials are provided."""
    has_credentials = bool(payload.client_id and payload.client_secret)

    perm_result: dict[str, Any] | None = None
    encrypted_secret = ""
    if has_credentials:
        validator = PermissionValidator()
        perm_result = await validator.validate(
            payload.client_id,
            payload.client_secret,
            payload.target_tenant_id,
        )
        crypto = CryptoService(settings)
        encrypted_secret = crypto.encrypt(payload.client_secret)

    project_id = str(uuid.uuid4())

    cosmos_client = request.app.state.cosmos_client
    database_name = ""
    if cosmos_client is not None:
        db_manager = ProjectDatabaseManager(cosmos_client)
        database_name = await db_manager.provision_project_database(project_id)

    now = datetime.now(UTC)
    project = Project(
        id=project_id,
        owner_id=user.oid,
        owner_email=user.email,
        name=payload.name,
        target_tenant_id=payload.target_tenant_id,
        target_tenant_name=payload.target_tenant_name,
        client_id=payload.client_id,
        encrypted_client_secret=encrypted_secret,
        database_name=database_name,
        status="active" if (perm_result and perm_result["valid"]) else "setup",
        permission_status=perm_result,
        created_at=now,
        updated_at=now,
    )
    saved = await repo.upsert_project(project)
    logger.info("Project created: %s (db=%s) by user %s", saved.id, database_name, user.oid)
    return _project_response(saved)


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Get project details."""
    project = await validate_project_access(project_id, user, repo, settings)
    return _project_response(project)


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    payload: UpdateProjectPayload,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Update project settings. Requires admin role."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="admin",
    )
    if payload.name is not None:
        project.name = payload.name
    if payload.sync_schedule_hours is not None:
        project.sync_schedule_hours = payload.sync_schedule_hours
    if payload.baseline_window_days is not None:
        project.baseline_window_days = payload.baseline_window_days
    project.updated_at = datetime.now(UTC)
    saved = await repo.upsert_project(project)
    return _project_response(saved)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Delete a project. Owner only."""
    project = await validate_project_access(project_id, user, repo, settings)
    if project.owner_id != user.oid and not settings.local_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the project owner can delete a project",
        )

    if project.database_name:
        cosmos_client = request.app.state.cosmos_client
        if cosmos_client is not None:
            db_manager = ProjectDatabaseManager(cosmos_client)
            await db_manager.delete_project_database(project.database_name)
        repo_cache = request.app.state.project_repo_cache
        if repo_cache is not None:
            repo_cache.evict(project.database_name)

    await repo.delete_project(project.owner_id, project_id)
    logger.info("Project deleted: %s (db=%s) by user %s", project_id, project.database_name, user.oid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/validate-permissions")
async def validate_permissions(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Re-validate Graph API permissions for a project's credentials."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="admin",
    )
    if not project.client_id or not project.encrypted_client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No app credentials configured. Use delegated scan mode or add credentials first.",
        )
    crypto = CryptoService(settings)
    secret = crypto.decrypt(project.encrypted_client_secret)

    validator = PermissionValidator()
    perm_result = await validator.validate(
        project.client_id,
        secret,
        project.target_tenant_id,
    )

    project.permission_status = perm_result
    project.status = "active" if perm_result["valid"] else "error"
    project.updated_at = datetime.now(UTC)
    await repo.upsert_project(project)
    return perm_result


@router.put("/{project_id}/credentials")
async def update_credentials(
    project_id: str,
    payload: UpdateCredentialsPayload,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Update project credentials and re-validate permissions. Admin only."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="admin",
    )

    validator = PermissionValidator()
    perm_result = await validator.validate(
        payload.client_id,
        payload.client_secret,
        project.target_tenant_id,
    )

    crypto = CryptoService(settings)
    project.client_id = payload.client_id
    project.encrypted_client_secret = crypto.encrypt(payload.client_secret)
    project.permission_status = perm_result
    project.status = "active" if perm_result["valid"] else "error"
    project.updated_at = datetime.now(UTC)
    saved = await repo.upsert_project(project)
    return _project_response(saved)


# ------------------------------------------------------------------
# Membership endpoints
# ------------------------------------------------------------------


@router.get("/{project_id}/members")
async def list_members(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """List project members and the caller's effective role."""
    project = await validate_project_access(project_id, user, repo, settings)
    members = await repo.list_project_members(project_id)

    if project.owner_id == user.oid:
        current_user_role = "owner"
    else:
        caller = next(
            (m for m in members if m.user_id == user.oid or m.email.lower() == user.email.lower()),
            None,
        )
        current_user_role = caller.role if caller else "viewer"

    result: list[dict[str, Any]] = [
        {
            "id": "owner",
            "user_id": project.owner_id,
            "email": project.owner_email,
            "role": "owner",
            "status": "accepted",
        }
    ]
    result.extend(m.model_dump(mode="json") for m in members)
    return {"members": result, "current_user_role": current_user_role}


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
async def invite_member(
    project_id: str,
    payload: InviteMemberPayload,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Invite a member to a project. Admin only."""
    project = await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="admin",
    )

    if payload.role not in ("admin", "operator", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be admin, operator, or viewer",
        )

    if payload.email.lower() == (project.owner_email or "").lower():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot invite the project owner as a member",
        )

    existing = await repo.get_project_member_by_email(project_id, payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A member with this email has already been invited",
        )

    member = ProjectMember(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=payload.email,
        email=payload.email,
        role=payload.role,
        invited_by=user.oid,
        status="accepted",
        created_at=datetime.now(UTC),
    )
    saved = await repo.upsert_project_member(member)
    logger.info("Member invited to project %s: %s", project_id, payload.email)
    return saved.model_dump(mode="json")


@router.put("/{project_id}/members/{member_id}")
async def update_member(
    project_id: str,
    member_id: str,
    payload: UpdateMemberPayload,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Update a member's role. Admin only."""
    await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="admin",
    )

    members = await repo.list_project_members(project_id)
    target = next((m for m in members if m.id == member_id), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if payload.role not in ("admin", "operator", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be admin, operator, or viewer",
        )

    target.role = payload.role
    saved = await repo.upsert_project_member(target)
    return saved.model_dump(mode="json")


@router.delete("/{project_id}/members/{member_id}")
async def remove_member(
    project_id: str,
    member_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: MasterRepo = Depends(get_master_repo),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Remove a member from a project. Admin only."""
    await validate_project_access(
        project_id,
        user,
        repo,
        settings,
        required_role="admin",
    )

    members = await repo.list_project_members(project_id)
    target = next((m for m in members if m.id == member_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    if target.user_id == user.oid or target.email.lower() == user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove yourself from the project",
        )

    await repo.delete_project_member(project_id, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
