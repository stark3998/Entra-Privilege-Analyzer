from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models.governance import ConnectorConfig, ConnectorDelivery, ConnectorType
from app.services.governance_repo import GovernanceRepo

SecretResolver = Callable[[str], Awaitable[str]]


class ConnectorDeliveryError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class ConnectorDispatcher:
    """Replay-safe outbound delivery with connector-specific payload envelopes."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=20)

    async def deliver(
        self,
        config: ConnectorConfig,
        delivery: ConnectorDelivery,
        payload: dict[str, Any],
        secret: str | None = None,
    ) -> ConnectorDelivery:
        if not config.enabled:
            raise ConnectorDeliveryError("Connector is disabled", retryable=False)
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": delivery.idempotency_key,
        }
        endpoint = config.endpoint
        if secret:
            if config.settings.get("secret_usage") == "endpoint":
                endpoint = secret
            else:
                header = str(config.settings.get("auth_header", "Authorization"))
                scheme = str(config.settings.get("auth_scheme", "Bearer")).strip()
                headers[header] = f"{scheme} {secret}".strip()
        _validate_public_https_endpoint(endpoint)
        envelope = self._envelope(config.connector_type, delivery.event_type, payload)
        try:
            response = await self._client.post(
                endpoint,
                headers=headers,
                json=envelope,
            )
        except httpx.RequestError as exc:
            raise ConnectorDeliveryError(
                "Connector network request failed",
                retryable=True,
            ) from exc
        now = datetime.now(UTC)
        attempts = delivery.attempts + 1
        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            return delivery.model_copy(
                update={
                    "status": "dead_letter" if attempts >= 5 or not retryable else "failed",
                    "attempts": attempts,
                    "next_attempt_at": now + timedelta(minutes=min(2**attempts, 60))
                    if retryable and attempts < 5
                    else None,
                    "last_error": f"Connector returned HTTP {response.status_code}",
                    "updated_at": now,
                }
            )
        return delivery.model_copy(
            update={
                "status": "delivered",
                "attempts": attempts,
                "next_attempt_at": None,
                "last_error": None,
                "updated_at": now,
            }
        )

    def _envelope(
        self,
        connector_type: ConnectorType,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if connector_type == ConnectorType.TEAMS:
            return {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "type": "AdaptiveCard",
                            "version": "1.5",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "weight": "Bolder",
                                    "text": event_type,
                                },
                                {"type": "TextBlock", "wrap": True, "text": str(payload)},
                            ],
                        },
                    }
                ],
            }
        if connector_type == ConnectorType.SERVICE_NOW:
            return {"short_description": event_type, "u_payload": payload}
        return {"eventType": event_type, "resource": payload}


class KeyVaultSecretResolver:
    """Resolve a Key Vault secret URI only at delivery time."""

    def __init__(
        self,
        token_provider: Callable[[str], Awaitable[str]],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._client = client or httpx.AsyncClient(timeout=10)

    async def resolve(self, secret_reference: str) -> str:
        parsed = urlparse(secret_reference)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not parsed.hostname.endswith(".vault.azure.net")
            or not parsed.path.startswith("/secrets/")
        ):
            raise ConnectorDeliveryError(
                "Connector secret reference must be an Azure Key Vault secret URI",
                retryable=False,
            )
        token = await self._token_provider("https://vault.azure.net/.default")
        try:
            response = await self._client.get(
                secret_reference,
                params={"api-version": "7.4"},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.RequestError as exc:
            raise ConnectorDeliveryError(
                "Key Vault network request failed",
                retryable=True,
            ) from exc
        if response.status_code >= 400:
            raise ConnectorDeliveryError(
                f"Key Vault returned HTTP {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        value = response.json().get("value")
        if not isinstance(value, str) or not value:
            raise ConnectorDeliveryError(
                "Key Vault secret response did not contain a value",
                retryable=False,
            )
        return value


class ConnectorDeliveryWorker:
    """Process due deliveries without persisting resolved connector secrets."""

    def __init__(
        self,
        repo: GovernanceRepo,
        dispatcher: ConnectorDispatcher,
        secret_resolver: SecretResolver,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher
        self._secret_resolver = secret_resolver

    async def process_due(
        self,
        project_id: str,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[ConnectorDelivery]:
        deliveries = await self._repo.list_due_deliveries(
            project_id,
            now=now or datetime.now(UTC),
            limit=limit,
        )
        results: list[ConnectorDelivery] = []
        for delivery in deliveries:
            config = await self._repo.get_connector(
                delivery.connector_id,
                project_id,
            )
            if config is None:
                updated = delivery.model_copy(
                    update={
                        "status": "dead_letter",
                        "attempts": delivery.attempts + 1,
                        "last_error": "Connector configuration not found",
                        "updated_at": datetime.now(UTC),
                    }
                )
            else:
                try:
                    secret = (
                        await self._secret_resolver(config.secret_reference)
                        if config.secret_reference
                        else None
                    )
                    updated = await self._dispatcher.deliver(
                        config,
                        delivery,
                        delivery.payload,
                        secret,
                    )
                except ConnectorDeliveryError as exc:
                    attempts = delivery.attempts + 1
                    updated = delivery.model_copy(
                        update={
                            "status": (
                                "failed"
                                if exc.retryable and attempts < 5
                                else "dead_letter"
                            ),
                            "attempts": attempts,
                            "next_attempt_at": (
                                datetime.now(UTC)
                                + timedelta(minutes=min(2**attempts, 60))
                                if exc.retryable and attempts < 5
                                else None
                            ),
                            "last_error": str(exc),
                            "updated_at": datetime.now(UTC),
                        }
                    )
            results.append(await self._repo.upsert_delivery(updated))
        return results


def _validate_public_https_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ConnectorDeliveryError(
            "Connector endpoint must use HTTPS",
            retryable=False,
        )
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "metadata.azure.internal"} or hostname.endswith(
        (".local", ".internal")
    ):
        raise ConnectorDeliveryError(
            "Connector endpoint cannot target an internal host",
            retryable=False,
        )
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ConnectorDeliveryError(
            "Connector endpoint cannot target a non-public address",
            retryable=False,
        )
