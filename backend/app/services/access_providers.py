from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.models.remediation import RemediationAction
from app.services.provider_errors import (
    ProviderFailureCategory,
    ProviderOperationError,
    ProviderOperationResult,
)

_ALLOWED_METHODS = {"DELETE", "PATCH", "POST", "PUT"}
_GRAPH_HOST = "graph.microsoft.com"
_ARM_HOST = "management.azure.com"


class HttpAccessProvider:
    """Deterministic HTTP mutation provider with dry-run and postconditions."""

    def __init__(
        self,
        provider: str,
        allowed_host: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._provider = provider
        self._allowed_host = allowed_host
        self._client = client or httpx.AsyncClient(timeout=30)

    async def execute(
        self,
        action: RemediationAction,
        access_token: str,
    ) -> ProviderOperationResult:
        payload = action.provider_payload
        method = str(payload.get("method", "")).upper()
        url = str(payload.get("url", ""))
        if method not in _ALLOWED_METHODS:
            raise ProviderOperationError(
                ProviderFailureCategory.INVALID_REQUEST,
                f"Unsupported mutation method: {method}",
                provider=self._provider,
                retryable=False,
            )
        parsed = httpx.URL(url)
        if parsed.scheme != "https" or parsed.host != self._allowed_host:
            raise ProviderOperationError(
                ProviderFailureCategory.INVALID_REQUEST,
                "Provider URL is outside the configured service boundary",
                provider=self._provider,
                retryable=False,
            )
        if not access_token:
            raise ProviderOperationError(
                ProviderFailureCategory.AUTHORIZATION,
                "Provider access token is required",
                provider=self._provider,
                retryable=False,
            )
        if action.dry_run:
            return ProviderOperationResult(
                provider=self._provider,
                operation_id=f"dry-run-{action.id}",
                details={
                    "dry_run": True,
                    "method": method,
                    "url": url,
                    "preconditions": action.preconditions,
                    "postconditions": action.postconditions,
                    "compensation": action.compensation,
                },
            )

        await self._verify_conditions(action.preconditions, access_token)
        response = await self._client.request(
            method,
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "client-request-id": action.correlation_id or str(uuid.uuid4()),
            },
            json=payload.get("body"),
        )
        if response.status_code >= 400:
            raise ProviderOperationError.from_http_status(
                response.status_code,
                _safe_error_message(response),
                provider=self._provider,
                error_code=_error_code(response),
                request_id=response.headers.get("request-id")
                or response.headers.get("x-ms-request-id"),
            )
        await self._verify_conditions(action.postconditions, access_token)
        return ProviderOperationResult(
            provider=self._provider,
            operation_id=response.headers.get("location") or action.id,
            request_id=response.headers.get("request-id")
            or response.headers.get("x-ms-request-id"),
            details={"status_code": response.status_code, "verified": True},
        )

    async def _verify_conditions(
        self,
        conditions: list[dict[str, Any]],
        access_token: str,
    ) -> None:
        for condition in conditions:
            url = str(condition.get("url", ""))
            parsed = httpx.URL(url)
            if parsed.scheme != "https" or parsed.host != self._allowed_host:
                raise ProviderOperationError(
                    ProviderFailureCategory.INVALID_REQUEST,
                    "Condition URL is outside the configured service boundary",
                    provider=self._provider,
                    retryable=False,
                )
            response = await self._client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            expected = int(condition.get("expected_status", 200))
            if response.status_code != expected:
                raise ProviderOperationError(
                    ProviderFailureCategory.CONFLICT,
                    "Provider condition was not satisfied",
                    provider=self._provider,
                    retryable=False,
                    status_code=response.status_code,
                    request_id=response.headers.get("request-id")
                    or response.headers.get("x-ms-request-id"),
                )


class GraphAccessProvider(HttpAccessProvider):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__("microsoft_graph", _GRAPH_HOST, client)


class ArmAccessProvider(HttpAccessProvider):
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        super().__init__("azure_resource_manager", _ARM_HOST, client)


class CompositeAccessProvider:
    def __init__(self, providers: dict[str, HttpAccessProvider]) -> None:
        self._providers = providers

    async def execute(
        self,
        action: RemediationAction,
        access_token: str,
    ) -> ProviderOperationResult:
        provider = self._providers.get(action.provider)
        if provider is None:
            raise ProviderOperationError(
                ProviderFailureCategory.UNSUPPORTED,
                f"No provider registered for {action.provider}",
                provider=action.provider,
                retryable=False,
            )
        return await provider.execute(action, access_token)


def _safe_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Provider returned HTTP {response.status_code}"
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"][:500]
    return f"Provider returned HTTP {response.status_code}"


def _error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    return str(error.get("code")) if isinstance(error, dict) and error.get("code") else None
