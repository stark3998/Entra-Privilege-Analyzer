"""Synchronous Graph API HTTP client with retry logic.

Mirrors the retry/throttle behaviour in backend/app/services/graph_ingest.py
but uses a sync httpx client (Azure Functions activities are synchronous).
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_BACKOFF = 1.0
_MAX_BACKOFF = 30.0


def _sanitize_url(url: str) -> str:
    """Strip query params for safe logging (params may contain filter values)."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(_MAX_BACKOFF, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(_MAX_BACKOFF, _BASE_BACKOFF * float(2 ** attempt))


def graph_get(
    token: str,
    url: str,
    params: dict[str, str] | None = None,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Issue a Graph GET with bounded retry handling for 429 throttling."""
    safe_url = _sanitize_url(url)

    with httpx.Client(timeout=timeout) as client:
        for attempt in range(_MAX_RETRIES + 1):
            start = time.monotonic()
            resp = client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            if resp.status_code == 429 and attempt < _MAX_RETRIES:
                delay = _retry_delay(resp, attempt)
                logger.warning(
                    "Graph 429 throttled | url=%s | retry_after=%.1fs | attempt=%d/%d | elapsed=%.0fms",
                    safe_url, delay, attempt + 1, _MAX_RETRIES, elapsed_ms,
                )
                time.sleep(delay)
                continue

            if resp.is_success:
                data = resp.json()
                item_count = len(data.get("value", []))
                has_next = "@odata.nextLink" in data
                logger.info(
                    "Graph 200 OK | url=%s | items=%d | has_next=%s | elapsed=%.0fms",
                    safe_url, item_count, has_next, elapsed_ms,
                )
                return data

            if resp.status_code == 403:
                error_body = resp.text[:500]
                logger.error(
                    "Graph 403 Forbidden | url=%s | elapsed=%.0fms | body=%s",
                    safe_url, elapsed_ms, error_body,
                )
                raise PermissionError(
                    f"Graph denied access to {safe_url}: {error_body}"
                )

            if resp.status_code == 404:
                logger.warning(
                    "Graph 404 Not Found | url=%s | elapsed=%.0fms | body=%s",
                    safe_url, elapsed_ms, resp.text[:300],
                )

            logger.error(
                "Graph %d error | url=%s | attempt=%d/%d | elapsed=%.0fms | body=%s",
                resp.status_code, safe_url, attempt + 1, _MAX_RETRIES + 1, elapsed_ms,
                resp.text[:500],
            )
            resp.raise_for_status()

    raise RuntimeError(f"Graph throttled {safe_url} after {_MAX_RETRIES} retries")


def graph_get_all_pages(
    token: str,
    url: str,
    params: dict[str, str] | None = None,
    *,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """Follow @odata.nextLink to collect all pages into a single list."""
    all_items: list[dict[str, Any]] = []
    current_url: str | None = url
    current_params = params
    page = 0

    while current_url is not None:
        data = graph_get(token, current_url, current_params, timeout=timeout)
        page_items = data.get("value", [])
        all_items.extend(page_items)
        page += 1
        current_url = data.get("@odata.nextLink")
        current_params = None

    safe_url = _sanitize_url(url)
    logger.info(
        "Graph pagination complete | url=%s | total_items=%d | pages=%d",
        safe_url, len(all_items), page,
    )
    return all_items
