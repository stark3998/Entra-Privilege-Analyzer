from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.project import ScanLogEntry
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)

_RECENT_EVENTS_MAX = 200


@dataclass(frozen=True, slots=True)
class _Subscriber:
    queue: asyncio.Queue[dict[str, Any]]
    scan_id: str | None


@dataclass(slots=True)
class _ProjectListener:
    pubsub: Any
    task: asyncio.Task[None]


class ScanEventBroker:
    """Project-scoped live event broker with Redis pub/sub fan-out when available."""

    def __init__(
        self,
        redis_cache: RedisCache | None = None,
        cosmos_repo: Any | None = None,
    ) -> None:
        self._redis_cache = redis_cache
        self._cosmos_repo = cosmos_repo
        self._subscribers: dict[str, set[_Subscriber]] = defaultdict(set)
        self._project_listeners: dict[str, _ProjectListener] = {}
        self._persist_tasks: set[asyncio.Task[None]] = set()
        self._lock = asyncio.Lock()
        self._recent_events: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=_RECENT_EVENTS_MAX)
        )

    @staticmethod
    def _channel_name(project_id: str) -> str:
        return f"scan-events:{project_id}"

    @staticmethod
    def _build_event(
        project_id: str,
        *,
        type: str,
        message: str,
        scan_id: str | None = None,
        level: str = "info",
        phase: str | None = None,
        status: str | None = None,
        items_processed: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        return {
            "id": f"{project_id}:{scan_id or 'project'}:{now.timestamp()}",
            "type": type,
            "message": message,
            "project_id": project_id,
            "scan_id": scan_id,
            "level": level,
            "phase": phase,
            "status": status,
            "items_processed": items_processed,
            "timestamp": now.isoformat(),
            "details": details or {},
        }

    @staticmethod
    def _matches_scan(event: dict[str, Any], scan_id: str | None) -> bool:
        if event.get("type") == "stream.error":
            return True
        if scan_id is None:
            return True
        return event.get("scan_id") == scan_id

    @staticmethod
    def _enqueue(queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(event)

    def _append_recent(self, project_id: str, event: dict[str, Any]) -> None:
        """Append an event to the per-project ring buffer for poll access."""
        self._recent_events[project_id].append(event)

    def get_events_after(
        self,
        project_id: str,
        scan_id: str | None = None,
        after_timestamp: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return buffered events newer than *after_timestamp*, optionally filtered by scan_id."""
        buf = self._recent_events.get(project_id)
        if buf is None:
            return []

        results: list[dict[str, Any]] = []
        for event in buf:
            if after_timestamp is not None and event.get("timestamp", "") <= after_timestamp:
                continue
            if not self._matches_scan(event, scan_id):
                continue
            results.append(event)
        return results

    async def _ensure_project_listener(self, project_id: str) -> None:
        if self._redis_cache is None or project_id in self._project_listeners:
            return
        pubsub = self._redis_cache.pubsub()
        channel = self._channel_name(project_id)
        await pubsub.subscribe(channel)
        task = asyncio.create_task(self._redis_listener(project_id, pubsub))
        self._project_listeners[project_id] = _ProjectListener(pubsub=pubsub, task=task)

    async def _stop_project_listener(self, project_id: str) -> None:
        listener = self._project_listeners.pop(project_id, None)
        if listener is None:
            return
        listener.task.cancel()
        await asyncio.gather(listener.task, return_exceptions=True)
        channel = self._channel_name(project_id)
        with contextlib.suppress(Exception):
            await listener.pubsub.unsubscribe(channel)
        with contextlib.suppress(Exception):
            await listener.pubsub.aclose()

    async def _fan_out(self, project_id: str, event: dict[str, Any]) -> None:
        self._append_recent(project_id, event)

        async with self._lock:
            subscribers = list(self._subscribers.get(project_id, set()))

        for subscriber in subscribers:
            if not self._matches_scan(event, subscriber.scan_id):
                continue
            self._enqueue(subscriber.queue, event)

    @asynccontextmanager
    async def subscribe(
        self,
        project_id: str,
        scan_id: str | None = None,
    ) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        subscriber = _Subscriber(queue=queue, scan_id=scan_id)
        async with self._lock:
            self._subscribers[project_id].add(subscriber)
            should_start_listener = (
                self._redis_cache is not None and project_id not in self._project_listeners
            )
        if should_start_listener:
            await self._ensure_project_listener(project_id)
        try:
            yield queue
        finally:
            should_stop_listener = False
            async with self._lock:
                subscribers = self._subscribers.get(project_id)
                if subscribers is not None:
                    subscribers.discard(subscriber)
                    if not subscribers:
                        self._subscribers.pop(project_id, None)
                        should_stop_listener = self._redis_cache is not None
            if should_stop_listener:
                await self._stop_project_listener(project_id)
            await drain_queue(queue)

    async def _redis_listener(
        self,
        project_id: str,
        pubsub: Any,
    ) -> None:
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                payload = message.get("data")
                if isinstance(payload, bytes):
                    payload = payload.decode("utf-8")
                if not isinstance(payload, str):
                    continue

                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("Discarding malformed scan event payload from Redis")
                    continue

                if not isinstance(event, dict):
                    logger.warning("Discarding non-object scan event payload from Redis")
                    continue

                if event.get("project_id") != project_id:
                    logger.warning("Discarding scan event with mismatched project binding")
                    continue

                if not isinstance(event.get("details"), dict):
                    event["details"] = {}

                await self._fan_out(project_id, event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            async with self._lock:
                listener = self._project_listeners.get(project_id)
                current_task = asyncio.current_task()
                if listener is not None and listener.task is current_task:
                    self._project_listeners.pop(project_id, None)
            logger.warning("Scan event listener stopped: %s", exc)
            await self._fan_out(
                project_id,
                self._build_event(
                    project_id,
                    type="stream.error",
                    message=(
                        "Live scan streaming lost its Redis connection. "
                        "Reconnect to continue receiving updates."
                    ),
                    level="error",
                    status="failed",
                ),
            )

    async def publish(
        self,
        project_id: str,
        *,
        type: str,
        message: str,
        scan_id: str | None = None,
        level: str = "info",
        phase: str | None = None,
        status: str | None = None,
        items_processed: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = self._build_event(
            project_id,
            scan_id=scan_id,
            type=type,
            message=message,
            level=level,
            phase=phase,
            status=status,
            items_processed=items_processed,
            details=details,
        )

        if self._cosmos_repo is not None and scan_id is not None:
            persist_task = asyncio.create_task(self._persist_log(event))
            self._persist_tasks.add(persist_task)
            persist_task.add_done_callback(self._persist_tasks.discard)

        if self._redis_cache is not None:
            self._append_recent(project_id, event)
            await self._redis_cache.publish(
                self._channel_name(project_id),
                json.dumps(event, separators=(",", ":")),
            )
            return

        await self._fan_out(project_id, event)

    async def _persist_log(self, event: dict[str, Any]) -> None:
        try:
            entry = ScanLogEntry(
                id=event["id"],
                scan_id=event["scan_id"],
                project_id=event["project_id"],
                type=event["type"],
                message=event["message"],
                level=event.get("level", "info"),
                phase=event.get("phase"),
                status=event.get("status"),
                items_processed=event.get("items_processed"),
                timestamp=datetime.fromisoformat(event["timestamp"]),
                details=event.get("details") or {},
            )
            await self._cosmos_repo.append_scan_log(entry)
        except Exception as exc:
            logger.warning("Failed to persist scan log %s: %s", event.get("id"), exc)

    async def close(self) -> None:
        """Close broker-owned resources."""
        listeners = list(self._project_listeners)
        for project_id in listeners:
            await self._stop_project_listener(project_id)


def encode_sse(event: dict[str, Any]) -> bytes:
    payload = json.dumps(event, separators=(",", ":"))
    name = event.get("type", "message")
    event_id = event.get("id", "")
    return f"id: {event_id}\nevent: {name}\ndata: {payload}\n\n".encode()


async def drain_queue(queue: asyncio.Queue[dict[str, Any]]) -> None:
    with contextlib.suppress(asyncio.QueueEmpty):
        while True:
            queue.get_nowait()
