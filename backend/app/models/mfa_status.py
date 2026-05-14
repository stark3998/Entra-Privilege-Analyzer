# backend/app/models/mfa_status.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

PHISHING_RESISTANT_METHODS: set[str] = {
    "fido2",
    "windowsHelloForBusiness",
    "certificateBasedAuthentication",
    "passKeyDeviceBound",
}

STRONG_MFA_METHODS: set[str] = {
    "microsoftAuthenticatorPush",
    "softwareOneTimePasscode",
    "hardwareOneTimePasscode",
}

WEAK_MFA_METHODS: set[str] = {
    "mobilePhone",
    "email",
}


def classify_strongest_method(methods: list[str]) -> str:
    method_set = set(methods)
    if method_set & PHISHING_RESISTANT_METHODS:
        return "phishing_resistant"
    if method_set & STRONG_MFA_METHODS:
        return "strong"
    if method_set & WEAK_MFA_METHODS:
        return "weak"
    return "none"


class MfaRegistrationRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    user_principal_name: str
    user_display_name: str
    is_admin: bool = False
    is_mfa_capable: bool = False
    is_mfa_registered: bool = False
    is_passwordless_capable: bool = False
    is_sspr_registered: bool = False
    methods_registered: list[str] = []
    user_type: str = "member"
    strongest_method_tier: str = "none"
    last_updated: datetime
