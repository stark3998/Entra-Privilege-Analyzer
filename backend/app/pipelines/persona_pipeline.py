from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.governance import PersonaRole
from app.models.identity import IdentityProfile
from app.services.governance_repo import GovernanceRepo
from app.services.persona_lifecycle import PersonaLifecycleService


class PersonaPipeline:
    """Materializes reusable personas from stable peer cohorts."""

    def __init__(
        self,
        project_repo: Any,
        governance_repo: GovernanceRepo,
        persona_service: PersonaLifecycleService,
    ) -> None:
        self._project_repo = project_repo
        self._governance_repo = governance_repo
        self._persona_service = persona_service

    async def run(self, tenant_id: str) -> dict[str, int]:
        identities: list[IdentityProfile] = []
        offset = 0
        while True:
            page, total = await self._project_repo.list_identities(
                offset=offset,
                limit=200,
            )
            identities.extend(page)
            offset += len(page)
            if not page or offset >= total:
                break

        cohorts: dict[str, list[IdentityProfile]] = defaultdict(list)
        for identity in identities:
            if identity.identity_type.value == "User":
                cohort = self._human_cohort(identity)
            else:
                cohort = f"workload:{identity.identity_type.value}"
            cohorts[cohort].append(identity)

        existing = await self._governance_repo.list_personas(tenant_id)
        latest_by_name: dict[str, PersonaRole] = {}
        for persona in existing:
            current = latest_by_name.get(persona.name)
            if current is None or persona.version > current.version:
                latest_by_name[persona.name] = persona

        created = 0
        skipped = 0
        for cohort, members in cohorts.items():
            if len(members) < 2:
                skipped += len(members)
                continue
            persona = self._persona_service.build_persona(
                tenant_id,
                cohort,
                members,
                latest_by_name.get(cohort),
            )
            await self._governance_repo.upsert_persona(persona)
            created += 1
        return {
            "identities": len(identities),
            "personas_created": created,
            "identities_skipped": skipped,
        }

    def _human_cohort(self, identity: IdentityProfile) -> str:
        role_names = sorted(role.role_name for role in identity.current_roles)
        if role_names:
            return f"human:{'|'.join(role_names[:3])}"
        return "human:unassigned"
