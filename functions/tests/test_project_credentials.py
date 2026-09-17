from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FUNCTIONS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_ROOT))

from utils import project_credentials  # noqa: E402


def _encrypt(plaintext: str, key: bytes) -> str:
    nonce = b"123456789012"
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
    return f"v1:{base64.b64encode(nonce + ciphertext).decode()}"


def test_load_project_graph_credentials_resolves_and_decrypts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = bytes(range(32))
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.test")
    monkeypatch.setenv("COSMOS_KEY", "cosmos-key")
    monkeypatch.setenv("COSMOS_MASTER_DATABASE", "entra-master")
    monkeypatch.setenv("ENCRYPTION_KEY", base64.b64encode(key).decode())

    container = MagicMock()
    container.query_items.return_value = [
        {
            "client_id": "client-id",
            "encrypted_client_secret": _encrypt("client-secret", key),
            "target_tenant_id": "tenant-id",
        }
    ]
    database = MagicMock()
    database.get_container_client.return_value = container
    client = MagicMock()
    client.get_database_client.return_value = database
    monkeypatch.setattr(project_credentials, "_get_client", lambda *_args: client)

    credentials = project_credentials.load_project_graph_credentials(
        {"project_id": "project-id", "tenant_id": "tenant-id"}
    )

    assert credentials == ("client-id", "client-secret")
    container.query_items.assert_called_once()


def test_load_project_graph_credentials_rejects_tenant_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = os.urandom(32)
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.test")
    monkeypatch.setenv("COSMOS_KEY", "cosmos-key")
    monkeypatch.setenv("COSMOS_MASTER_DATABASE", "entra-master")
    monkeypatch.setenv("ENCRYPTION_KEY", base64.b64encode(key).decode())

    container = MagicMock()
    container.query_items.return_value = [
        {
            "client_id": "client-id",
            "encrypted_client_secret": _encrypt("client-secret", key),
            "target_tenant_id": "different-tenant",
        }
    ]
    database = MagicMock()
    database.get_container_client.return_value = container
    client = MagicMock()
    client.get_database_client.return_value = database
    monkeypatch.setattr(project_credentials, "_get_client", lambda *_args: client)

    with pytest.raises(RuntimeError, match="does not match"):
        project_credentials.load_project_graph_credentials(
            {"project_id": "project-id", "tenant_id": "tenant-id"}
        )
