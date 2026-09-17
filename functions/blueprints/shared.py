"""Shared constants and helpers for all scan blueprints."""

from __future__ import annotations

import os

import azure.durable_functions as df

RETRY_OPTIONS = df.RetryOptions(
    first_retry_interval_in_milliseconds=5000,
    max_number_of_attempts=3,
)

DEFAULT_GRAPH_API_VERSION = "beta"


def cosmos_config(payload: dict) -> dict:
    """Resolve Cosmos settings without persisting credentials in orchestration history."""
    endpoint = os.environ.get("COSMOS_ENDPOINT")
    key = os.environ.get("COSMOS_KEY")
    master_database = os.environ.get("COSMOS_MASTER_DATABASE") or os.environ.get(
        "COSMOS_DATABASE"
    )
    if not endpoint or not key or not master_database:
        raise RuntimeError(
            "COSMOS_ENDPOINT, COSMOS_KEY, and COSMOS_MASTER_DATABASE must be configured"
        )

    return {
        "endpoint": endpoint,
        "key": key,
        "database": payload["cosmos_database"],
        "master_database": master_database,
    }
