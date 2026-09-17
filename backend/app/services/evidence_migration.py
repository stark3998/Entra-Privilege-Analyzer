from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from azure.cosmos.exceptions import CosmosResourceExistsError

from app.models.tenant_evidence import ActivityEvidence, EvidenceLineage, EvidenceNode
from app.services.project_repo import ProjectRepo
from app.services.tenant_evidence_repo import TenantEvidenceRepo


class ProjectEvidenceMigrator:
    """Replay-safe incremental copy from legacy project evidence to tenant evidence."""

    def __init__(
        self,
        project_repo: ProjectRepo,
        tenant_repo: TenantEvidenceRepo,
    ) -> None:
        self._project_repo = project_repo
        self._tenant_repo = tenant_repo

    async def migrate(self, tenant_id: str, project_id: str, scan_id: str) -> dict[str, int]:
        identities_migrated = 0
        offset = 0
        while True:
            identities, total = await self._project_repo.list_identities(
                offset=offset,
                limit=200,
            )
            for identity in identities:
                await self._tenant_repo.upsert_identity_node(
                    EvidenceNode(
                        id=identity.id,
                        tenant_id=tenant_id,
                        node_type=identity.identity_type.value,
                        source_id=identity.object_id,
                        display_name=identity.display_name,
                        attributes={
                            "upn": identity.upn,
                            "app_id": identity.app_id,
                            "project_source": project_id,
                        },
                        valid_from=identity.created_at,
                        observed_at=identity.updated_at,
                        source="project_migration",
                    )
                )
                identities_migrated += 1
            offset += len(identities)
            if not identities or offset >= total:
                break

        actions_migrated = 0
        async for action in self._project_repo.stream_action_events():
            evidence_id = _stable_id("activity", tenant_id, action.id)
            await self._tenant_repo.upsert_activity(
                ActivityEvidence(
                    id=action.id,
                    tenant_id=tenant_id,
                    principal_id=action.identity_id,
                    action=action.action,
                    source=action.source.value,
                    occurred_at=action.timestamp,
                    resource_id=action.resource,
                    resource_type=action.resource_type,
                    result=action.result,
                    correlation_id=action.correlation_id,
                    evidence_id=evidence_id,
                )
            )
            try:
                await self._tenant_repo.create_lineage(
                    EvidenceLineage(
                        id=evidence_id,
                        evidence_id=evidence_id,
                        tenant_id=tenant_id,
                        source=f"project:{project_id}",
                        source_record_id=action.id,
                        scan_id=scan_id,
                        collected_at=action.timestamp,
                        normalized_at=datetime.now(UTC),
                        transformation_version="project-migration-v1",
                    )
                )
            except CosmosResourceExistsError:
                pass
            actions_migrated += 1
        return {"identities": identities_migrated, "actions": actions_migrated}


def _stable_id(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()
