from __future__ import annotations

import sys
from pathlib import Path

FUNCTIONS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_ROOT))

from blueprints.scan_bp import validate_scan_payload  # noqa: E402


def test_scan_payload_rejects_secrets() -> None:
    error = validate_scan_payload(
        {
            "tenant_id": "tenant-id",
            "project_id": "project-id",
            "scan_id": "scan-id",
            "cosmos_database": "project-project-id",
            "client_secret": "must-not-be-persisted",
        }
    )

    assert error is not None
    assert "must not be included" in error


def test_scan_payload_accepts_identifiers_only() -> None:
    error = validate_scan_payload(
        {
            "tenant_id": "tenant-id",
            "project_id": "project-id",
            "scan_id": "scan-id",
            "cosmos_database": "project-project-id",
        }
    )

    assert error is None
