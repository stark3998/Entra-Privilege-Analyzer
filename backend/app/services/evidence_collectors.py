from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from app.models.tenant_evidence import ActivityEvidence, CollectionCursor, DataQualityStatus
from app.services.provider_errors import ProviderOperationError
from app.services.tenant_evidence_repo import TenantEvidenceRepo


class EvidenceAdapter(Protocol):
    source: str

    async def collect(
        self,
        tenant_id: str,
        cursor: str | None,
    ) -> AsyncIterator[tuple[ActivityEvidence, str | None]]: ...


class PagedHttpEvidenceAdapter:
    """Read-only adapter for trusted Graph or ARM endpoints with explicit paging."""

    def __init__(
        self,
        *,
        source: str,
        initial_url: str,
        allowed_host: str,
        access_token: str,
        principal_field: str,
        action_field: str,
        timestamp_field: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.source = source
        self._initial_url = initial_url
        self._allowed_host = allowed_host
        self._token = access_token
        self._principal_field = principal_field
        self._action_field = action_field
        self._timestamp_field = timestamp_field
        self._client = client or httpx.AsyncClient(timeout=30)

    async def collect(
        self,
        tenant_id: str,
        cursor: str | None,
    ) -> AsyncIterator[tuple[ActivityEvidence, str | None]]:
        url: str | None = cursor or self._initial_url
        while url:
            parsed = httpx.URL(url)
            if parsed.scheme != "https" or parsed.host != self._allowed_host:
                raise ValueError("Evidence continuation URL crossed the provider boundary")
            response = await self._client.get(
                url,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if response.status_code >= 400:
                raise ProviderOperationError.from_http_status(
                    response.status_code,
                    f"{self.source} evidence collection failed",
                    provider=self.source,
                    request_id=response.headers.get("request-id")
                    or response.headers.get("x-ms-request-id"),
                )
            payload = response.json()
            records = payload.get("value", [])
            next_link = payload.get("@odata.nextLink") or payload.get("nextLink")
            for record in records:
                principal_id = str(_field(record, self._principal_field) or "")
                action = str(_field(record, self._action_field) or "")
                occurred_at = _parse_datetime(_field(record, self._timestamp_field))
                if not principal_id or not action or occurred_at is None:
                    continue
                source_id = str(record.get("id") or _stable_id(str(record)))
                evidence_id = _stable_id(tenant_id, self.source, source_id)
                yield (
                    ActivityEvidence(
                        id=source_id,
                        tenant_id=tenant_id,
                        principal_id=principal_id,
                        action=action,
                        source=self.source,
                        occurred_at=occurred_at,
                        resource_id=str(record.get("resourceId") or "") or None,
                        resource_type=str(record.get("resourceType") or "") or None,
                        result=str(record.get("result") or "success"),
                        correlation_id=str(record.get("correlationId") or "") or None,
                        evidence_id=evidence_id,
                        attributes={"source_record": record},
                    ),
                    str(next_link) if next_link else None,
                )
            url = str(next_link) if next_link else None


class EvidenceCollectionService:
    def __init__(self, repo: TenantEvidenceRepo) -> None:
        self._repo = repo

    async def run(
        self,
        tenant_id: str,
        adapter: EvidenceAdapter,
        cursor: str | None = None,
        legal_hold: bool = False,
    ) -> DataQualityStatus:
        count = 0
        first: datetime | None = None
        last: datetime | None = None
        latest_cursor = cursor
        await self._repo.upsert_collection_cursor(
            CollectionCursor(
                id=adapter.source,
                source=adapter.source,
                tenant_id=tenant_id,
                cursor=cursor,
                updated_at=datetime.now(UTC),
                status="running",
            )
        )
        try:
            async for event, next_cursor in adapter.collect(tenant_id, cursor):
                if legal_hold:
                    event = event.model_copy(update={"ttl": -1})
                await self._repo.upsert_activity(event)
                count += 1
                first = min(first, event.occurred_at) if first else event.occurred_at
                last = max(last, event.occurred_at) if last else event.occurred_at
                latest_cursor = next_cursor or latest_cursor
        except ProviderOperationError as exc:
            await self._repo.upsert_collection_cursor(
                CollectionCursor(
                    id=adapter.source,
                    source=adapter.source,
                    tenant_id=tenant_id,
                    cursor=latest_cursor,
                    watermark=last,
                    updated_at=datetime.now(UTC),
                    status="throttled" if exc.retryable else "failed",
                    error=str(exc),
                )
            )
            raise
        now = datetime.now(UTC)
        await self._repo.upsert_collection_cursor(
            CollectionCursor(
                id=adapter.source,
                source=adapter.source,
                tenant_id=tenant_id,
                cursor=latest_cursor,
                watermark=last,
                updated_at=now,
                status="ready",
            )
        )
        coverage_days = (last - first).days + 1 if first and last else 0
        quality = DataQualityStatus(
            id=adapter.source,
            source=adapter.source,
            tenant_id=tenant_id,
            assessed_at=now,
            coverage_start=first,
            coverage_end=last,
            completeness=min(coverage_days / 90, 1.0),
            confidence=1.0 if count else 0.0,
            gaps=[] if coverage_days >= 90 else ["less_than_90_days_of_evidence"],
        )
        return await self._repo.upsert_data_quality(quality)


def _field(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _stable_id(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()
