from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from app.models.governance import (
    AccessEdgeSnapshot,
    AccessSnapshot,
    RestoreConflict,
    RestorePlan,
)
from app.services.crypto import CryptoService


class SnapshotRestoreService:
    def __init__(self, crypto: CryptoService) -> None:
        self._crypto = crypto

    def create_snapshot(
        self,
        *,
        tenant_id: str,
        project_id: str,
        identity_id: str,
        workflow_id: str,
        edges: list[AccessEdgeSnapshot],
        created_by: str,
        retention_days: int = 365,
        legal_hold: bool = False,
    ) -> AccessSnapshot:
        canonical = json.dumps(
            [edge.model_dump(mode="json") for edge in sorted(edges, key=lambda item: item.id)],
            sort_keys=True,
            separators=(",", ":"),
        )
        now = datetime.now(UTC)
        return AccessSnapshot(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project_id,
            identity_id=identity_id,
            workflow_id=workflow_id,
            encrypted_payload=self._crypto.encrypt(canonical),
            payload_hash=hashlib.sha256(canonical.encode()).hexdigest(),
            edge_count=len(edges),
            created_at=now,
            created_by=created_by,
            legal_hold=legal_hold,
            retention_until=None if legal_hold else now + timedelta(days=retention_days),
        )

    def read_snapshot(self, snapshot: AccessSnapshot) -> list[AccessEdgeSnapshot]:
        plaintext = self._crypto.decrypt(snapshot.encrypted_payload)
        if hashlib.sha256(plaintext.encode()).hexdigest() != snapshot.payload_hash:
            raise ValueError("Snapshot integrity verification failed")
        payload = json.loads(plaintext)
        edges = [AccessEdgeSnapshot.model_validate(item) for item in payload]
        if len(edges) != snapshot.edge_count:
            raise ValueError("Snapshot edge count does not match payload")
        return edges

    def build_restore_plan(
        self,
        snapshot: AccessSnapshot,
        current_edges: list[AccessEdgeSnapshot],
        workflow_mutated_edge_ids: set[str],
    ) -> RestorePlan:
        original = {edge.id: edge for edge in self.read_snapshot(snapshot)}
        current = {edge.id: edge for edge in current_edges}
        restore: list[AccessEdgeSnapshot] = []
        preserve: list[AccessEdgeSnapshot] = []
        conflicts: list[RestoreConflict] = []
        for edge_id, edge in original.items():
            current_edge = current.get(edge_id)
            if current_edge is None:
                restore.append(edge)
            elif current_edge == edge:
                preserve.append(current_edge)
            elif edge_id in workflow_mutated_edge_ids:
                restore.append(edge)
            else:
                conflicts.append(
                    RestoreConflict(
                        edge_id=edge_id,
                        reason="Current access changed outside the workflow",
                        snapshot_edge=edge,
                        current_edge=current_edge,
                    )
                )
        for edge_id, edge in current.items():
            if edge_id not in original and edge_id not in workflow_mutated_edge_ids:
                preserve.append(edge)
        return RestorePlan(
            snapshot_id=snapshot.id,
            workflow_id=snapshot.workflow_id,
            restore_edges=restore,
            preserve_edges=preserve,
            conflicts=conflicts,
            requires_approval=bool(conflicts),
            generated_at=datetime.now(UTC),
        )
