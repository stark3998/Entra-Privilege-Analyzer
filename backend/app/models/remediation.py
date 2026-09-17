# backend/app/models/remediation.py
"""Pydantic v2 models for remediation action workflow."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RemediationActionType(StrEnum):
    """Types of remediation actions that can be performed via Graph API."""

    REMOVE_ROLE = "remove_role"
    CREATE_PIM_ELIGIBLE = "create_pim_eligible"
    DISABLE_ACCOUNT = "disable_account"
    REMOVE_GROUP_MEMBER = "remove_group_member"
    REVOKE_CONSENT = "revoke_consent"
    REMOVE_APP_CREDENTIAL = "remove_app_credential"
    CONVERT_PERMANENT_TO_PIM = "convert_permanent_to_pim"
    CREATE_CUSTOM_ROLE = "create_custom_role"
    UPDATE_CUSTOM_ROLE = "update_custom_role"
    DELETE_CUSTOM_ROLE = "delete_custom_role"
    ASSIGN_ENTRA_ROLE = "assign_entra_role"
    ASSIGN_AZURE_ROLE = "assign_azure_role"
    REMOVE_AZURE_ROLE = "remove_azure_role"
    CREATE_PIM_AZURE_ELIGIBLE = "create_pim_azure_eligible"
    ADD_GROUP_MEMBER = "add_group_member"
    GRANT_APP_PERMISSION = "grant_app_permission"
    ADD_FEDERATED_CREDENTIAL = "add_federated_credential"
    ENABLE_ACCOUNT = "enable_account"


class RemediationStatus(StrEnum):
    """Workflow status of a remediation action."""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RemediationAuditEventType(StrEnum):
    """Immutable lifecycle events for a remediation action."""

    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_SUCCEEDED = "execution_succeeded"
    EXECUTION_FAILED = "execution_failed"
    COMPENSATION_STARTED = "compensation_started"
    COMPENSATION_SUCCEEDED = "compensation_succeeded"
    COMPENSATION_FAILED = "compensation_failed"


class RemediationAction(BaseModel):
    """A single remediation action targeting an identity or resource."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    project_id: str
    correlation_id: str = ""
    idempotency_key: str = ""
    action_type: RemediationActionType
    target_identity_id: str
    target_resource_id: str | None = None
    target_display_name: str = ""
    requested_by: str
    approved_by: str | None = None
    status: RemediationStatus = RemediationStatus.PENDING
    justification: str = ""
    error_message: str | None = None
    created_at: datetime
    approved_at: datetime | None = None
    completed_at: datetime | None = None
    graph_operation: str = ""  # description of the Graph API call
    provider_operation_id: str | None = None
    provider_request_id: str | None = None
    failure_category: str | None = None
    failure_retryable: bool = False
    dry_run: bool = False
    provider: str = "microsoft_graph"
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    postconditions: list[dict[str, Any]] = Field(default_factory=list)
    compensation: dict[str, Any] | None = None


class RemediationAuditEvent(BaseModel):
    """Create-only, hash-chained evidence for one lifecycle transition."""

    model_config = ConfigDict(extra="ignore")

    id: str
    action_id: str
    project_id: str
    tenant_id: str
    sequence: int
    event_type: RemediationAuditEventType
    actor_id: str
    status: RemediationStatus
    occurred_at: datetime
    correlation_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str | None = None
    event_hash: str
    schema_version: int = 1
