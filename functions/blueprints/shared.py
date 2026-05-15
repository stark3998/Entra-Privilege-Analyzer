"""Shared constants and helpers for all scan blueprints."""

from __future__ import annotations

import azure.durable_functions as df

RETRY_OPTIONS = df.RetryOptions(
    first_retry_interval_in_milliseconds=5000,
    max_number_of_attempts=3,
)

DEFAULT_GRAPH_API_VERSION = "beta"


def cosmos_config(payload: dict) -> dict:
    """Extract Cosmos connection params from the orchestration payload."""
    return {
        "endpoint": payload["cosmos_endpoint"],
        "key": payload["cosmos_key"],
        "database": payload["cosmos_database"],
    }
