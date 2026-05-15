# backend/app/models/sod_policy.py
"""Configurable Separation of Duties conflict rules with built-in defaults."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SodConflictRule(BaseModel):
    """A single SoD conflict pair for a tenant."""

    model_config = ConfigDict(extra="ignore")

    id: str
    tenant_id: str
    role_a_name: str
    role_b_name: str
    severity: str = "high"  # critical | high | medium | low
    rationale: str = ""
    is_custom: bool = False  # False = built-in default, True = tenant-added
    enabled: bool = True


DEFAULT_SOD_RULES: list[dict[str, str]] = [
    {
        "role_a": "Global Administrator",
        "role_b": "Privileged Role Administrator",
        "severity": "critical",
        "rationale": "Tier 0 self-governance",
    },
    {
        "role_a": "Global Administrator",
        "role_b": "Security Administrator",
        "severity": "critical",
        "rationale": "Full control + security policy",
    },
    {
        "role_a": "Global Administrator",
        "role_b": "Application Administrator",
        "severity": "critical",
        "rationale": "Identity + app management overlap",
    },
    {
        "role_a": "Global Administrator",
        "role_b": "Conditional Access Administrator",
        "severity": "critical",
        "rationale": "Can exempt self from controls",
    },
    {
        "role_a": "Privileged Role Administrator",
        "role_b": "Application Administrator",
        "severity": "critical",
        "rationale": "Role assignment + app credential = takeover",
    },
    {
        "role_a": "Privileged Role Administrator",
        "role_b": "Helpdesk Administrator",
        "severity": "high",
        "rationale": "Role governance + password reset",
    },
    {
        "role_a": "Privileged Role Administrator",
        "role_b": "Security Administrator",
        "severity": "high",
        "rationale": "Role assignment + security policy bypass",
    },
    {
        "role_a": "Application Administrator",
        "role_b": "User Administrator",
        "severity": "high",
        "rationale": "App credential + password reset escalation",
    },
    {
        "role_a": "Application Administrator",
        "role_b": "Cloud Application Administrator",
        "severity": "high",
        "rationale": "Redundant high-privilege app roles",
    },
    {
        "role_a": "User Administrator",
        "role_b": "Authentication Administrator",
        "severity": "high",
        "rationale": "Both can reset passwords",
    },
    {
        "role_a": "Exchange Administrator",
        "role_b": "Compliance Administrator",
        "severity": "high",
        "rationale": "Exfiltrate + hide evidence",
    },
    {
        "role_a": "Exchange Administrator",
        "role_b": "SharePoint Administrator",
        "severity": "medium",
        "rationale": "Cross-workload data exfiltration",
    },
    {
        "role_a": "Intune Administrator",
        "role_b": "User Administrator",
        "severity": "high",
        "rationale": "Device + user lifecycle lateral movement",
    },
    {
        "role_a": "Privileged Authentication Administrator",
        "role_b": "User Administrator",
        "severity": "critical",
        "rationale": "Admin password reset + user lifecycle",
    },
    {
        "role_a": "Application Administrator",
        "role_b": "Privileged Authentication Administrator",
        "severity": "critical",
        "rationale": "App impersonation + admin takeover",
    },
    {
        "role_a": "Groups Administrator",
        "role_b": "Privileged Role Administrator",
        "severity": "high",
        "rationale": "Group membership + role assignment backdoor",
    },
    {
        "role_a": "Conditional Access Administrator",
        "role_b": "Authentication Administrator",
        "severity": "high",
        "rationale": "Policy exemption + credential management",
    },
    {
        "role_a": "Billing Administrator",
        "role_b": "Global Administrator",
        "severity": "medium",
        "rationale": "No financial oversight",
    },
    {
        "role_a": "Security Administrator",
        "role_b": "Security Reader",
        "severity": "medium",
        "rationale": "Redundant, violates least privilege",
    },
    {
        "role_a": "Directory Synchronization Accounts",
        "role_b": "Privileged Role Administrator",
        "severity": "high",
        "rationale": "On-prem to cloud escalation",
    },
]


def build_default_rules(tenant_id: str) -> list[SodConflictRule]:
    """Generate SodConflictRule objects from DEFAULT_SOD_RULES for a tenant."""
    rules: list[SodConflictRule] = []
    for idx, entry in enumerate(DEFAULT_SOD_RULES):
        rules.append(
            SodConflictRule(
                id=f"sod_{tenant_id}_{idx}",
                tenant_id=tenant_id,
                role_a_name=entry["role_a"],
                role_b_name=entry["role_b"],
                severity=entry["severity"],
                rationale=entry["rationale"],
                is_custom=False,
                enabled=True,
            )
        )
    return rules
