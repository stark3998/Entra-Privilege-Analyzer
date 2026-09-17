from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings

_FORBIDDEN_FIELDS = {
    "access_token",
    "client_secret",
    "cosmos_key",
    "connection_string",
    "encryption_key",
}


class AgentGateway:
    """Calls the durable Agent Framework service with identifier-only payloads."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.agent_function_app_url:
            raise RuntimeError("AGENT_FUNCTION_APP_URL is not configured")
        if not settings.local_mode and not settings.agent_function_app_url.startswith(
            "https://"
        ):
            raise RuntimeError("AGENT_FUNCTION_APP_URL must use HTTPS")
        self._endpoint = settings.agent_function_app_url.rstrip("/")
        self._function_key = settings.agent_function_key
        self._client = client or httpx.AsyncClient(timeout=60)

    async def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        forbidden = _find_forbidden_fields(payload)
        if forbidden:
            raise ValueError(
                f"Agent payload contains forbidden fields: {', '.join(sorted(forbidden))}"
            )
        headers = {"Content-Type": "application/json"}
        if self._function_key:
            headers["x-functions-key"] = self._function_key
        response = await self._client.post(
            f"{self._endpoint}/api/agent/query",
            headers=headers,
            json=payload,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Agent service returned HTTP {response.status_code}")
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
            raise RuntimeError("Agent service returned an invalid response")
        return result


def _find_forbidden_fields(value: Any) -> set[str]:
    if isinstance(value, dict):
        matches = {str(key) for key in value if str(key).lower() in _FORBIDDEN_FIELDS}
        for nested in value.values():
            matches.update(_find_forbidden_fields(nested))
        return matches
    if isinstance(value, list):
        matches: set[str] = set()
        for nested in value:
            matches.update(_find_forbidden_fields(nested))
        return matches
    return set()
