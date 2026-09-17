from __future__ import annotations

from azure.cosmos.aio import ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.models.tenant_evidence import (
    ActionFeatureAggregate,
    ActivityEvidence,
    CollectionCursor,
    DataQualityStatus,
    EntitlementEdge,
    EvidenceLineage,
    EvidenceNode,
)


class TenantEvidenceRepo:
    def __init__(
        self,
        identity_nodes: ContainerProxy,
        resource_nodes: ContainerProxy,
        entitlement_nodes: ContainerProxy,
        entitlement_edges: ContainerProxy,
        activity_events: ContainerProxy,
        action_features: ContainerProxy,
        evidence_lineage: ContainerProxy,
        collection_cursors: ContainerProxy,
        data_quality: ContainerProxy,
    ) -> None:
        self._identity_nodes = identity_nodes
        self._resource_nodes = resource_nodes
        self._entitlement_nodes = entitlement_nodes
        self._entitlement_edges = entitlement_edges
        self._activity_events = activity_events
        self._action_features = action_features
        self._evidence_lineage = evidence_lineage
        self._collection_cursors = collection_cursors
        self._data_quality = data_quality

    @classmethod
    async def create(cls, db: DatabaseProxy) -> TenantEvidenceRepo:
        return cls(
            identity_nodes=db.get_container_client("identity_nodes"),
            resource_nodes=db.get_container_client("resource_nodes"),
            entitlement_nodes=db.get_container_client("entitlement_nodes"),
            entitlement_edges=db.get_container_client("entitlement_edges"),
            activity_events=db.get_container_client("activity_events"),
            action_features=db.get_container_client("action_features"),
            evidence_lineage=db.get_container_client("evidence_lineage"),
            collection_cursors=db.get_container_client("collection_cursors"),
            data_quality=db.get_container_client("data_quality"),
        )

    async def upsert_identity_node(self, node: EvidenceNode) -> EvidenceNode:
        result = await self._identity_nodes.upsert_item(body=node.model_dump(mode="json"))
        return EvidenceNode.model_validate(result)

    async def upsert_resource_node(self, node: EvidenceNode) -> EvidenceNode:
        result = await self._resource_nodes.upsert_item(body=node.model_dump(mode="json"))
        return EvidenceNode.model_validate(result)

    async def upsert_entitlement_node(self, node: EvidenceNode) -> EvidenceNode:
        result = await self._entitlement_nodes.upsert_item(body=node.model_dump(mode="json"))
        return EvidenceNode.model_validate(result)

    async def upsert_entitlement_edge(self, edge: EntitlementEdge) -> EntitlementEdge:
        result = await self._entitlement_edges.upsert_item(body=edge.model_dump(mode="json"))
        return EntitlementEdge.model_validate(result)

    async def upsert_activity(self, activity: ActivityEvidence) -> ActivityEvidence:
        result = await self._activity_events.upsert_item(
            body=activity.model_dump(mode="json")
        )
        return ActivityEvidence.model_validate(result)

    async def upsert_action_feature(
        self,
        feature: ActionFeatureAggregate,
    ) -> ActionFeatureAggregate:
        result = await self._action_features.upsert_item(
            body=feature.model_dump(mode="json")
        )
        return ActionFeatureAggregate.model_validate(result)

    async def get_entitlement_edge(
        self,
        edge_id: str,
        principal_id: str,
    ) -> EntitlementEdge | None:
        try:
            item = await self._entitlement_edges.read_item(
                item=edge_id,
                partition_key=principal_id,
            )
            return EntitlementEdge.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def create_lineage(self, lineage: EvidenceLineage) -> EvidenceLineage:
        result = await self._evidence_lineage.create_item(
            body=lineage.model_dump(mode="json")
        )
        return EvidenceLineage.model_validate(result)

    async def list_entitlement_edges(
        self,
        principal_id: str,
    ) -> list[EntitlementEdge]:
        return [
            EntitlementEdge.model_validate(item)
            async for item in self._entitlement_edges.query_items(
                query="SELECT * FROM c WHERE c.principal_id = @principalId",
                parameters=[{"name": "@principalId", "value": principal_id}],
                partition_key=principal_id,
            )
        ]

    async def list_data_quality(self, tenant_id: str) -> list[DataQualityStatus]:
        return [
            DataQualityStatus.model_validate(item)
            async for item in self._data_quality.query_items(
                query="SELECT * FROM c WHERE c.tenant_id = @tenantId",
                parameters=[{"name": "@tenantId", "value": tenant_id}],
            )
        ]

    async def upsert_collection_cursor(self, cursor: CollectionCursor) -> CollectionCursor:
        result = await self._collection_cursors.upsert_item(
            body=cursor.model_dump(mode="json")
        )
        return CollectionCursor.model_validate(result)

    async def upsert_data_quality(self, quality: DataQualityStatus) -> DataQualityStatus:
        result = await self._data_quality.upsert_item(
            body=quality.model_dump(mode="json")
        )
        return DataQualityStatus.model_validate(result)
