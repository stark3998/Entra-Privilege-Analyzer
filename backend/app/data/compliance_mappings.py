# backend/app/data/compliance_mappings.py
"""Static mapping of ViolationType values to compliance framework control IDs."""

from __future__ import annotations

COMPLIANCE_MAPPINGS: dict[str, dict[str, list[dict[str, str]]]] = {
    "stale_identity": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC6.2", "name": "Access provisioning/deprovisioning"},
        ],
        "iso27001": [
            {"id": "A.5.16", "name": "Identity management"},
            {"id": "A.5.18", "name": "Access rights lifecycle"},
        ],
        "nist80053": [
            {"id": "AC-2", "name": "Account management"},
            {"id": "AC-2(3)", "name": "Disable accounts"},
        ],
    },
    "permanent_admin": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC6.3", "name": "Role-based access changes"},
        ],
        "iso27001": [
            {"id": "A.5.18", "name": "Access rights"},
            {"id": "A.8.2", "name": "Privileged access"},
        ],
        "nist80053": [
            {"id": "AC-6(5)", "name": "Privileged accounts"},
            {"id": "AC-6(2)", "name": "Non-privileged access"},
        ],
    },
    "no_pim": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC6.3", "name": "Role-based access changes"},
        ],
        "iso27001": [
            {"id": "A.5.18", "name": "Access rights"},
            {"id": "A.8.2", "name": "Privileged access"},
        ],
        "nist80053": [
            {"id": "AC-6", "name": "Least privilege"},
            {"id": "AC-6(1)", "name": "Authorize access to security functions"},
            {"id": "AC-6(5)", "name": "Privileged accounts"},
        ],
    },
    "overprivileged": {
        "soc2": [
            {"id": "CC6.3", "name": "Least privilege in access changes"},
        ],
        "iso27001": [
            {"id": "A.5.15", "name": "Access control"},
            {"id": "A.5.18", "name": "Access rights lifecycle"},
        ],
        "nist80053": [
            {"id": "AC-6", "name": "Least privilege"},
            {
                "id": "AC-6(10)",
                "name": "Prohibit non-privileged users from executing privileged functions",
            },
        ],
    },
    "separation_of_duties": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC5.1", "name": "Segregation of duties"},
        ],
        "iso27001": [
            {"id": "A.5.3", "name": "Segregation of duties"},
        ],
        "nist80053": [
            {"id": "AC-5", "name": "Separation of duties"},
        ],
    },
    "sp_credential_expiry": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC6.6", "name": "System boundary protection"},
        ],
        "iso27001": [
            {"id": "A.5.17", "name": "Authentication information"},
            {"id": "A.8.5", "name": "Secure authentication"},
        ],
        "nist80053": [
            {"id": "IA-5", "name": "Authenticator management"},
        ],
    },
    "mfa_gap": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC6.6", "name": "System boundary protection"},
        ],
        "iso27001": [
            {"id": "A.5.17", "name": "Authentication information"},
            {"id": "A.8.5", "name": "Secure authentication"},
        ],
        "nist80053": [
            {"id": "IA-2", "name": "Identification and authentication"},
            {"id": "IA-2(1)", "name": "MFA for privileged accounts"},
        ],
    },
    "ca_legacy_auth_not_blocked": {
        "soc2": [
            {"id": "CC6.6", "name": "System boundary protection"},
        ],
        "iso27001": [
            {"id": "A.8.5", "name": "Secure authentication"},
            {"id": "A.8.20", "name": "Network security"},
        ],
        "nist80053": [
            {"id": "AC-17", "name": "Remote access"},
            {"id": "IA-2(6)", "name": "Access to accounts - separate device"},
        ],
    },
    "guest_stale": {
        "soc2": [
            {"id": "CC6.1", "name": "Logical access security"},
            {"id": "CC6.2", "name": "Access provisioning/deprovisioning"},
        ],
        "iso27001": [
            {"id": "A.5.19", "name": "Information security in supplier relationships"},
        ],
        "nist80053": [
            {"id": "AC-2(5)", "name": "Inactivity logout"},
            {"id": "AC-17(1)", "name": "Monitoring and control"},
        ],
    },
}


def get_compliance_controls(
    violation_type: str,
    framework: str,
) -> list[dict[str, str]]:
    """Return compliance controls for a violation type and framework.

    Returns an empty list when the violation type or framework is not mapped.
    """
    return COMPLIANCE_MAPPINGS.get(violation_type, {}).get(framework, [])


SUPPORTED_FRAMEWORKS: list[str] = ["soc2", "iso27001", "nist80053"]
