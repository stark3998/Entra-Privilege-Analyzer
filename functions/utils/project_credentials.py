"""Resolve project Graph credentials inside activities, outside durable history."""

from __future__ import annotations

import base64
import os
from typing import Any

from azure.cosmos import CosmosClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_VERSION_PREFIX = "v1:"
_client_cache: dict[str, CosmosClient] = {}


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} must be configured")
    return value


def _get_client(endpoint: str, key: str) -> CosmosClient:
    cache_key = f"{endpoint}:{key[:12]}"
    if cache_key not in _client_cache:
        _client_cache[cache_key] = CosmosClient(endpoint, credential=key)
    return _client_cache[cache_key]


def _decrypt(ciphertext: str, encoded_key: str) -> str:
    if not ciphertext.startswith(_VERSION_PREFIX):
        raise ValueError("Unsupported project credential ciphertext version")

    key = base64.b64decode(encoded_key, validate=True)
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must decode to exactly 32 bytes")

    raw = base64.b64decode(ciphertext[len(_VERSION_PREFIX) :], validate=True)
    if len(raw) < 29:
        raise ValueError("Project credential ciphertext is malformed")

    return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode()


def load_project_graph_credentials(payload: dict[str, Any]) -> tuple[str, str]:
    """Load and decrypt a project's Graph app credentials for one activity."""
    endpoint = _required_env("COSMOS_ENDPOINT")
    key = _required_env("COSMOS_KEY")
    master_database = os.environ.get("COSMOS_MASTER_DATABASE") or _required_env(
        "COSMOS_DATABASE"
    )
    encryption_key = _required_env("ENCRYPTION_KEY")

    project_id = str(payload["project_id"])
    tenant_id = str(payload["tenant_id"])
    container = (
        _get_client(endpoint, key)
        .get_database_client(master_database)
        .get_container_client("projects")
    )
    query = (
        "SELECT TOP 1 c.client_id, c.encrypted_client_secret, c.target_tenant_id "
        "FROM c WHERE c.id = @projectId"
    )
    items = list(
        container.query_items(
            query=query,
            parameters=[{"name": "@projectId", "value": project_id}],
            enable_cross_partition_query=True,
        )
    )
    if not items:
        raise RuntimeError(f"Project {project_id} was not found")

    project = items[0]
    if project.get("target_tenant_id") != tenant_id:
        raise RuntimeError("Project tenant does not match orchestration tenant")

    client_id = project.get("client_id")
    encrypted_secret = project.get("encrypted_client_secret")
    if not client_id or not encrypted_secret:
        raise RuntimeError(f"Project {project_id} has no Graph app credentials")

    return str(client_id), _decrypt(str(encrypted_secret), encryption_key)
