# backend/app/models/app_registration.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CredentialInfo(BaseModel):
    key_id: str
    display_name: str | None = None
    credential_type: str  # "password" | "certificate"
    start_date_time: datetime | None = None
    end_date_time: datetime | None = None
    days_until_expiry: int | None = None
    age_days: int | None = None
    is_expired: bool = False


class RequestedPermission(BaseModel):
    resource_app_id: str
    resource_display_name: str | None = None
    permission_id: str
    permission_type: str  # "Role" (application) | "Scope" (delegated)
    permission_value: str | None = None


class AppOwner(BaseModel):
    id: str
    display_name: str | None = None
    user_principal_name: str | None = None
    owner_type: str = "User"


HIGH_RISK_APP_PERMISSION_GUIDS: set[str] = {
    "19dbc75e-c2e2-444c-a770-ec596d67a9eb",  # Directory.ReadWrite.All
    "9e3f62cf-ca93-4989-b6ce-bf83d28f9fe8",  # RoleManagement.ReadWrite.Directory
    "e2a3a72e-5f79-4c64-b1b1-878b674786c9",  # Mail.ReadWrite
    "b633e1c5-b582-4048-a93e-9f11b44c7e96",  # Mail.Send
    "06b708a9-e830-4db3-a914-8e69da51d44f",  # AppRoleAssignment.ReadWrite.All
    "1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9",  # Application.ReadWrite.All
}


class AppRegistrationProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    app_id: str
    display_name: str
    sign_in_audience: str = "AzureADMyOrg"
    is_multi_tenant: bool = False
    created_date_time: datetime | None = None
    disabled_by_microsoft: str | None = None
    verified_publisher_name: str | None = None
    password_credentials: list[CredentialInfo] = []
    key_credentials: list[CredentialInfo] = []
    owners: list[AppOwner] = []
    owner_count: int = 0
    requested_permissions: list[RequestedPermission] = []
    total_app_permissions: int = 0
    total_delegated_permissions: int = 0
    high_risk_permissions: list[str] = []
    fetched_at: datetime
