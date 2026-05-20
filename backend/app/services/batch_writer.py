from __future__ import annotations

import asyncio
import logging
from typing import Any

from azure.cosmos.aio import ContainerProxy
from azure.cosmos.exceptions import CosmosHttpResponseError

logger = logging.getLogger(__name__)

_BATCH_CONCURRENCY = 25
_TRANSACTIONAL_BATCH_MAX = 100


class BatchWriter:
    """Buffers documents and flushes via Cosmos transactional batches."""

    def __init__(
        self,
        container: ContainerProxy,
        pk_field: str,
        max_buffer: int = 500,
    ) -> None:
        self._container = container
        self._pk_field = pk_field
        self._max_buffer = max_buffer
        self._buffer: dict[str, list[dict[str, Any]]] = {}
        self._total_buffered = 0
        self._semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

    def add(self, body: dict[str, Any]) -> None:
        pk_value = str(body.get(self._pk_field, body.get("id", "")))
        self._buffer.setdefault(pk_value, []).append(body)
        self._total_buffered += 1

    @property
    def should_flush(self) -> bool:
        return self._total_buffered >= self._max_buffer

    async def flush(self) -> int:
        if not self._buffer:
            return 0
        tasks = []
        for pk_value, docs in self._buffer.items():
            for i in range(0, len(docs), _TRANSACTIONAL_BATCH_MAX):
                chunk = docs[i : i + _TRANSACTIONAL_BATCH_MAX]
                tasks.append(self._execute_batch(pk_value, chunk))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        written = 0
        for r in results:
            if isinstance(r, int):
                written += r
            elif isinstance(r, Exception):
                logger.error("Batch flush error: %s", r)
        self._buffer.clear()
        self._total_buffered = 0
        return written

    async def _execute_batch(self, pk_value: str, docs: list[dict[str, Any]]) -> int:
        async with self._semaphore:
            batch_ops = [("upsert", (doc,), {}) for doc in docs]
            try:
                await self._container.execute_item_batch(
                    batch_operations=batch_ops,
                    partition_key=pk_value,
                )
                return len(docs)
            except CosmosHttpResponseError:
                return await self._fallback_upsert(docs)

    async def _fallback_upsert(self, docs: list[dict[str, Any]]) -> int:
        async def _single(doc: dict[str, Any]) -> bool:
            async with self._semaphore:
                try:
                    await self._container.upsert_item(body=doc)
                    return True
                except CosmosHttpResponseError as exc:
                    logger.warning(
                        "Fallback upsert failed for %s: %s", doc.get("id", "?"), exc.message,
                    )
                    return False

        results = await asyncio.gather(*(_single(doc) for doc in docs))
        return sum(1 for ok in results if ok)
