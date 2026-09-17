from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime

from app.data.builtin_roles import find_matching_azure_roles, find_matching_entra_roles
from app.models.governance import PersonaRole, PersonaStatus
from app.models.identity import IdentityProfile
from app.models.role import RoleScope
from app.services.role_mapper import RoleMapper


class PersonaLifecycleService:
    """Builds reusable, versioned least-privilege personas from peer evidence."""

    def __init__(
        self,
        mapper: RoleMapper,
        *,
        common_threshold: float = 0.6,
        rare_min_observations: int = 3,
    ) -> None:
        self._mapper = mapper
        self._common_threshold = common_threshold
        self._rare_min_observations = rare_min_observations

    def build_persona(
        self,
        tenant_id: str,
        name: str,
        identities: list[IdentityProfile],
        previous: PersonaRole | None = None,
    ) -> PersonaRole:
        if len(identities) < 2:
            raise ValueError("A reusable persona requires at least two peer identities")
        permission_sets: list[set[str]] = []
        action_counts: Counter[str] = Counter()
        for identity in identities:
            permissions, _ = self._mapper.map_identity_permissions(identity)
            permission_sets.append(permissions)
            for observed in identity.observed_actions:
                action_counts[observed.action] += observed.count

        frequency = Counter(permission for values in permission_sets for permission in values)
        common = sorted(
            permission
            for permission, count in frequency.items()
            if count / len(identities) >= self._common_threshold
        )
        rare = sorted(
            permission
            for permission, count in frequency.items()
            if permission not in common and count >= self._rare_min_observations
        )
        required = set(common) | set(rare)
        is_azure = any(
            role.scope.startswith("/subscriptions")
            for identity in identities
            for role in identity.current_roles
        )
        scope = RoleScope.AZURE if is_azure else RoleScope.ENTRA
        matches = (
            find_matching_azure_roles(required)
            if is_azure
            else find_matching_entra_roles(required)
        )
        best = matches[0] if matches else None
        digest = hashlib.sha256(
            f"{tenant_id}:{name}:{','.join(common)}:{','.join(rare)}".encode()
        ).hexdigest()[:16]
        version = previous.version + 1 if previous else 1
        now = datetime.now(UTC)
        return PersonaRole(
            id=f"persona-{digest}-v{version}",
            tenant_id=tenant_id,
            name=name,
            version=version,
            status=PersonaStatus.DRAFT,
            member_identity_ids=sorted(identity.id for identity in identities),
            common_permissions=common,
            justified_rare_permissions=rare,
            builtin_role_id=best.role_id if best else None,
            builtin_role_name=best.role_name if best else None,
            match_score=best.match_score if best else 0.0,
            custom_role_definition=None
            if best and best.match_score >= 0.95 and not best.excess_permissions
            else {
                "name": f"Persona-{name}-v{version}",
                "scope": scope.value,
                "permissions": sorted(required),
                "is_assignable_scopes": ["/"],
            },
            created_at=previous.created_at if previous else now,
            updated_at=now,
        )

    def transition(
        self,
        persona: PersonaRole,
        target: PersonaStatus,
        actor: str,
    ) -> PersonaRole:
        allowed = {
            PersonaStatus.DRAFT: {PersonaStatus.EVALUATING, PersonaStatus.RETIRED},
            PersonaStatus.EVALUATING: {PersonaStatus.APPROVED, PersonaStatus.DRAFT},
            PersonaStatus.APPROVED: {PersonaStatus.PUBLISHED, PersonaStatus.DRAFT},
            PersonaStatus.PUBLISHED: {PersonaStatus.SUPERSEDED, PersonaStatus.RETIRED},
            PersonaStatus.SUPERSEDED: {PersonaStatus.RETIRED},
            PersonaStatus.RETIRED: set(),
        }
        if target not in allowed[persona.status]:
            raise ValueError(f"Invalid persona transition: {persona.status} -> {target}")
        return persona.model_copy(
            update={
                "status": target,
                "updated_at": datetime.now(UTC),
                "approved_by": actor if target == PersonaStatus.APPROVED else persona.approved_by,
            }
        )
