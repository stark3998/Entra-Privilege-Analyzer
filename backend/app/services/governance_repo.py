from __future__ import annotations

from datetime import datetime
from typing import Any, TypeVar

from azure.cosmos.aio import ContainerProxy, DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from pydantic import BaseModel

from app.models.governance import (
    AccessSnapshot,
    ApprovalPolicy,
    AuthorizationConfiguration,
    ConnectorConfig,
    ConnectorDelivery,
    GovernanceWorkflow,
    PersonaRole,
    RiskAssessment,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class GovernanceRepo:
    def __init__(self, db: DatabaseProxy) -> None:
        self._personas = db.get_container_client("personas")
        self._risk = db.get_container_client("risk_assessments")
        self._workflows = db.get_container_client("governance_workflows")
        self._policies = db.get_container_client("approval_policies")
        self._authorization = db.get_container_client("authorization_configs")
        self._safety_gates = db.get_container_client("safety_gate_decisions")
        self._snapshots = db.get_container_client("access_snapshots")
        self._connectors = db.get_container_client("connector_configs")
        self._deliveries = db.get_container_client("connector_deliveries")

    async def _upsert(
        self,
        container: ContainerProxy,
        model: ModelT,
        model_type: type[ModelT],
    ) -> ModelT:
        result = await container.upsert_item(body=model.model_dump(mode="json"))
        return model_type.model_validate(result)

    async def _read(
        self,
        container: ContainerProxy,
        item_id: str,
        partition_key: str,
        model_type: type[ModelT],
    ) -> ModelT | None:
        try:
            item = await container.read_item(item=item_id, partition_key=partition_key)
            return model_type.model_validate(item)
        except CosmosResourceNotFoundError:
            return None

    async def _query(
        self,
        container: ContainerProxy,
        model_type: type[ModelT],
        query: str,
        parameters: list[dict[str, Any]],
        **kwargs: Any,
    ) -> list[ModelT]:
        return [
            model_type.model_validate(item)
            async for item in container.query_items(
                query=query,
                parameters=parameters,
                **kwargs,
            )
        ]

    async def upsert_risk_assessment(self, value: RiskAssessment) -> RiskAssessment:
        return await self._upsert(self._risk, value, RiskAssessment)

    async def list_risk_assessments(self, identity_id: str) -> list[RiskAssessment]:
        return await self._query(
            self._risk,
            RiskAssessment,
            "SELECT * FROM c WHERE c.identity_id = @identityId ORDER BY c.computed_at DESC",
            [{"name": "@identityId", "value": identity_id}],
            partition_key=identity_id,
        )

    async def upsert_persona(self, value: PersonaRole) -> PersonaRole:
        return await self._upsert(self._personas, value, PersonaRole)

    async def list_personas(self, tenant_id: str) -> list[PersonaRole]:
        return await self._query(
            self._personas,
            PersonaRole,
            "SELECT * FROM c WHERE c.tenant_id = @tenantId",
            [{"name": "@tenantId", "value": tenant_id}],
            partition_key=tenant_id,
        )

    async def upsert_workflow(self, value: GovernanceWorkflow) -> GovernanceWorkflow:
        return await self._upsert(self._workflows, value, GovernanceWorkflow)

    async def get_workflow(
        self,
        workflow_id: str,
        identity_id: str,
    ) -> GovernanceWorkflow | None:
        return await self._read(
            self._workflows,
            workflow_id,
            identity_id,
            GovernanceWorkflow,
        )

    async def find_workflow(self, workflow_id: str) -> GovernanceWorkflow | None:
        items = await self._query(
            self._workflows,
            GovernanceWorkflow,
            "SELECT TOP 1 * FROM c WHERE c.id = @id",
            [{"name": "@id", "value": workflow_id}],
        )
        return items[0] if items else None

    async def find_workflow_by_idempotency_key(
        self,
        project_id: str,
        idempotency_key: str,
    ) -> GovernanceWorkflow | None:
        items = await self._query(
            self._workflows,
            GovernanceWorkflow,
            (
                "SELECT TOP 1 * FROM c WHERE c.project_id = @projectId "
                "AND c.idempotency_key = @idempotencyKey"
            ),
            [
                {"name": "@projectId", "value": project_id},
                {"name": "@idempotencyKey", "value": idempotency_key},
            ],
        )
        return items[0] if items else None

    async def list_workflows(self, project_id: str) -> list[GovernanceWorkflow]:
        return await self._query(
            self._workflows,
            GovernanceWorkflow,
            "SELECT * FROM c WHERE c.project_id = @projectId ORDER BY c.updated_at DESC",
            [{"name": "@projectId", "value": project_id}],
        )

    async def upsert_policy(self, value: ApprovalPolicy) -> ApprovalPolicy:
        return await self._upsert(self._policies, value, ApprovalPolicy)

    async def get_policy(self, project_id: str) -> ApprovalPolicy | None:
        return await self._read(self._policies, "default", project_id, ApprovalPolicy)

    async def upsert_authorization(
        self,
        value: AuthorizationConfiguration,
    ) -> AuthorizationConfiguration:
        return await self._upsert(
            self._authorization,
            value,
            AuthorizationConfiguration,
        )

    async def get_authorization(
        self,
        project_id: str,
    ) -> AuthorizationConfiguration | None:
        return await self._read(
            self._authorization,
            "authorization",
            project_id,
            AuthorizationConfiguration,
        )

    async def upsert_snapshot(self, value: AccessSnapshot) -> AccessSnapshot:
        return await self._upsert(self._snapshots, value, AccessSnapshot)

    async def get_snapshot(
        self,
        snapshot_id: str,
        identity_id: str,
    ) -> AccessSnapshot | None:
        return await self._read(
            self._snapshots,
            snapshot_id,
            identity_id,
            AccessSnapshot,
        )

    async def upsert_connector(self, value: ConnectorConfig) -> ConnectorConfig:
        return await self._upsert(self._connectors, value, ConnectorConfig)

    async def list_connectors(self, project_id: str) -> list[ConnectorConfig]:
        return await self._query(
            self._connectors,
            ConnectorConfig,
            "SELECT * FROM c WHERE c.project_id = @projectId",
            [{"name": "@projectId", "value": project_id}],
            partition_key=project_id,
        )

    async def get_connector(
        self,
        connector_id: str,
        project_id: str,
    ) -> ConnectorConfig | None:
        return await self._read(
            self._connectors,
            connector_id,
            project_id,
            ConnectorConfig,
        )

    async def find_delivery_by_idempotency_key(
        self,
        project_id: str,
        idempotency_key: str,
    ) -> ConnectorDelivery | None:
        items = await self._query(
            self._deliveries,
            ConnectorDelivery,
            (
                "SELECT TOP 1 * FROM c WHERE c.project_id = @projectId "
                "AND c.idempotency_key = @idempotencyKey"
            ),
            [
                {"name": "@projectId", "value": project_id},
                {"name": "@idempotencyKey", "value": idempotency_key},
            ],
            partition_key=project_id,
        )
        return items[0] if items else None

    async def upsert_delivery(self, value: ConnectorDelivery) -> ConnectorDelivery:
        return await self._upsert(self._deliveries, value, ConnectorDelivery)

    async def list_due_deliveries(
        self,
        project_id: str,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[ConnectorDelivery]:
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.project_id = @project_id
              AND (c.status = 'pending'
                   OR (c.status = 'failed' AND c.next_attempt_at <= @now))
            ORDER BY c.created_at ASC
        """
        items = self._deliveries.query_items(
            query=query,
            parameters=[
                {"name": "@limit", "value": limit},
                {"name": "@project_id", "value": project_id},
                {"name": "@now", "value": now.isoformat()},
            ],
            partition_key=project_id,
        )
        return [ConnectorDelivery.model_validate(item) async for item in items]
