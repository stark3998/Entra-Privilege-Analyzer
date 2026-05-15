# backend/app/models/remediation.py
"""Pydantic v2 models for remediation action workflow."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RemediationActionType(StrEnum):
    """Types of remediation actions that can be performed via Graph API."""

    REMOVE_ROLE = "remove_role"
    CREATE_PIM_ELIGIBLE = "create_pim_eligible"
    DISABLE_ACCOUNT = "disable_account"
    REMOVE_GROUP_MEMBER = "remove_group_member"
    REVOKE_CONSENT = "revoke_consent"
    REMOVE_APP_CREDENTIAL = "remove_app_credential"
    CONVERT_PERMANENT_TO_PIM = "convert_permanent_to_pim"


class RemediationStatus(StrEnum):
    """Workflow status of a remediation action."""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class RemediationAction(BaseModel):
    """A single remediation action targeting an identity or resource."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    project_id: str
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
