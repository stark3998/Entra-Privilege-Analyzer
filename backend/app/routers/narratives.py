# backend/app/routers/narratives.py
"""API endpoints for AI-generated narratives."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import CurrentUser, require_role, validate_tenant_access
from app.config import Settings, get_settings
from app.models.narrative import NarrativeScope
from app.services.cosmos import CosmosRepo, get_cosmos_repo
from app.services.foundry import FoundryClient, get_foundry_client
from app.services.narrative_engine import NarrativeEngine

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tenants/{tenant_id}/narratives",
    tags=["narratives"],
)


def _get_engine(
    repo: CosmosRepo,
    foundry: FoundryClient | None,
) -> NarrativeEngine:
    """Build a NarrativeEngine, raising 503 if Foundry is unavailable."""
    if foundry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI narrative generation is not configured",
        )
    return NarrativeEngine(client=foundry, repo=repo)


@router.get("/executive")
async def get_executive_narrative(
    tenant_id: str,
    user: CurrentUser = Depends(
        require_role("Executive", "IAMAdmin", "SecurityEngineer"),
    ),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    foundry: FoundryClient | None = Depends(get_foundry_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return the executive AI narrative digest for a tenant."""
    validate_tenant_access(tenant_id, user, settings)

    engine = _get_engine(repo, foundry)
    narrative = await engine.get_or_generate(
        tenant_id, NarrativeScope.EXECUTIVE, "tenant",
    )
    return narrative.model_dump(mode="json")


@router.get("/identity/{identity_id}")
async def get_identity_narrative(
    tenant_id: str,
    identity_id: str,
    user: CurrentUser = Depends(
        require_role("SecurityEngineer", "IAMAdmin"),
    ),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    foundry: FoundryClient | None = Depends(get_foundry_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Return the AI narrative summary for a specific identity."""
    validate_tenant_access(tenant_id, user, settings)

    engine = _get_engine(repo, foundry)
    narrative = await engine.get_or_generate(
        tenant_id, NarrativeScope.IDENTITY, identity_id,
    )
    return narrative.model_dump(mode="json")


@router.post("/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_narratives(
    tenant_id: str,
    user: CurrentUser = Depends(require_role("IAMAdmin")),
    repo: CosmosRepo = Depends(get_cosmos_repo),
    foundry: FoundryClient | None = Depends(get_foundry_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Force regeneration of all narratives for a tenant."""
    validate_tenant_access(tenant_id, user, settings)

    logger.info(
        "audit.narratives.refresh tenant=%s user=%s",
        tenant_id,
        user.oid,
    )

    engine = _get_engine(repo, foundry)
    # Regenerate executive digest (always)
    await engine.generate_executive_digest(tenant_id)

    return {"status": "accepted", "message": "Narrative regeneration started"}
