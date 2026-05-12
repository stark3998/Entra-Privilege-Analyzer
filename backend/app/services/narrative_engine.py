# backend/app/services/narrative_engine.py
"""AI narrative generation engine using FoundryClient."""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from app.models.narrative import Narrative, NarrativeScope
from app.services.cosmos import CosmosRepo
from app.services.foundry import FoundryClient

logger = logging.getLogger(__name__)

_NARRATIVE_TTL_HOURS = 24


def _sanitize_for_prompt(value: str, max_len: int = 200) -> str:
    """Strip control chars and truncate to prevent prompt injection."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", value)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    return cleaned[:max_len]


class NarrativeEngine:
    """Generates and caches AI-powered narratives for various scopes."""

    def __init__(self, client: FoundryClient, repo: CosmosRepo) -> None:
        self._client = client
        self._repo = repo

    async def generate_executive_digest(self, tenant_id: str) -> Narrative:
        """Generate an executive summary paragraph for the tenant dashboard.

        Aggregates dashboard data, sends it to Foundry, and caches the result.
        """
        summary = await self._repo.get_dashboard_summary(tenant_id)

        system_prompt = (
            "You are a concise security analyst writing for C-level executives. "
            "Produce a 2-3 sentence executive digest highlighting the most important "
            "risk trends, drift alerts, and compliance posture. Use plain English, "
            "no bullet points. Include specific numbers."
        )
        user_prompt = (
            f"Tenant dashboard data:\n"
            f"- Total identities: {summary.get('total_identities', 0)}\n"
            f"- Average risk score: {summary.get('avg_risk_score', 0.0):.1f}\n"
            f"- High-risk identities (score > 70): {summary.get('high_risk_count', 0)}\n"
            f"- Open drift alerts: {summary.get('drift_alerts_open', 0)}\n"
            f"- Drift by severity: {summary.get('drift_alerts_by_severity', {})}\n"
            f"- Compliance score: {summary.get('compliance_score', 0.0):.1f}%\n"
            f"- Recommendations count: {summary.get('recommendations_count', 0)}\n"
            f"- Avg privilege reduction: {summary.get('avg_reduction_score', 0.0):.1f}%\n"
            f"\nWrite a brief executive digest."
        )

        content = await self._client.complete(system_prompt, user_prompt)
        now = datetime.now(UTC)
        narrative = Narrative(
            id=f"{NarrativeScope.EXECUTIVE}_tenant",
            tenant_id=tenant_id,
            scope=NarrativeScope.EXECUTIVE,
            scope_id="tenant",
            content=content,
            generated_at=now,
            expires_at=now + timedelta(hours=_NARRATIVE_TTL_HOURS),
        )
        await self._repo.upsert_narrative(tenant_id, narrative)
        return narrative

    async def generate_identity_summary(
        self, tenant_id: str, identity_id: str,
    ) -> Narrative:
        """Generate a narrative summary for a specific identity."""
        identity = await self._repo.get_identity(tenant_id, identity_id)
        if identity is None:
            now = datetime.now(UTC)
            return Narrative(
                id=f"{NarrativeScope.IDENTITY}_{identity_id}",
                tenant_id=tenant_id,
                scope=NarrativeScope.IDENTITY,
                scope_id=identity_id,
                content="Identity not found.",
                generated_at=now,
                expires_at=now + timedelta(hours=_NARRATIVE_TTL_HOURS),
            )

        # Gather related data
        drift_alerts, _ = await self._repo.list_drift_alerts(
            tenant_id=tenant_id, identity_id=identity_id, offset=0, limit=10,
        )
        recommendation = await self._repo.get_recommendation(tenant_id, identity_id)

        system_prompt = (
            "You are a security analyst writing a brief identity risk summary. "
            "Produce 2-3 sentences covering the identity's risk profile, active roles, "
            "recent drift alerts, and any recommendations. Be specific with numbers."
        )
        roles_text = ", ".join(r.role_name for r in identity.current_roles) or "None"
        drift_text = f"{len(drift_alerts)} active alert(s)" if drift_alerts else "No active drift"
        rec_text = (
            f"Recommended {recommendation.reduction_score:.0f}% privilege reduction"
            if recommendation
            else "No recommendation computed"
        )

        user_prompt = (
            f"Identity: {_sanitize_for_prompt(identity.display_name)} "
            f"({_sanitize_for_prompt(str(identity.identity_type))})\n"
            f"Risk score: {identity.risk_score:.1f}\n"
            f"Current roles: {_sanitize_for_prompt(roles_text, 500)}\n"
            f"Action count: {identity.action_count}\n"
            f"Drift: {_sanitize_for_prompt(drift_text)}\n"
            f"Recommendation: {_sanitize_for_prompt(rec_text)}\n"
            f"\nWrite a brief identity risk summary."
        )

        content = await self._client.complete(system_prompt, user_prompt)
        now = datetime.now(UTC)
        narrative = Narrative(
            id=f"{NarrativeScope.IDENTITY}_{identity_id}",
            tenant_id=tenant_id,
            scope=NarrativeScope.IDENTITY,
            scope_id=identity_id,
            content=content,
            generated_at=now,
            expires_at=now + timedelta(hours=_NARRATIVE_TTL_HOURS),
        )
        await self._repo.upsert_narrative(tenant_id, narrative)
        return narrative

    async def get_or_generate(
        self,
        tenant_id: str,
        scope: NarrativeScope,
        scope_id: str,
    ) -> Narrative:
        """Return a cached narrative if still valid, otherwise generate a new one."""
        narrative_id = f"{scope}_{scope_id}"
        existing = await self._repo.get_narrative(tenant_id, narrative_id)

        if existing is not None and existing.expires_at > datetime.now(UTC):
            return existing

        if scope == NarrativeScope.EXECUTIVE:
            return await self.generate_executive_digest(tenant_id)
        if scope == NarrativeScope.IDENTITY:
            return await self.generate_identity_summary(tenant_id, scope_id)

        # Fallback for other scopes
        now = datetime.now(UTC)
        return Narrative(
            id=narrative_id,
            tenant_id=tenant_id,
            scope=scope,
            scope_id=scope_id,
            content="Narrative generation is not available for this scope.",
            generated_at=now,
            expires_at=now + timedelta(hours=_NARRATIVE_TTL_HOURS),
        )
