from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.services.scan_events import ScanEventBroker


class _FakePubSub:
    def __init__(self) -> None:
        self.channels: set[str] = set()
        self.messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.closed = False
        self.raise_on_get = False

    async def subscribe(self, channel: str) -> None:
        self.channels.add(channel)

    async def unsubscribe(self, channel: str) -> None:
        self.channels.discard(channel)

    async def get_message(
        self,
        *,
        ignore_subscribe_messages: bool,
        timeout: float,
    ) -> dict[str, Any] | None:
        if self.raise_on_get:
            raise RuntimeError("redis listener failed")
        try:
            return self.messages.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def aclose(self) -> None:
        self.closed = True


class _FakeRedisCache:
    def __init__(self) -> None:
        self._pubsubs: list[_FakePubSub] = []

    def pubsub(self) -> _FakePubSub:
        pubsub = _FakePubSub()
        self._pubsubs.append(pubsub)
        return pubsub

    async def publish(self, channel: str, message: str) -> None:
        for pubsub in self._pubsubs:
            if channel in pubsub.channels:
                await pubsub.messages.put({"data": message})


@pytest.mark.asyncio
async def test_redis_backplane_delivers_matching_scan_events() -> None:
    broker = ScanEventBroker(redis_cache=_FakeRedisCache())

    async with broker.subscribe("project-001", scan_id="scan-001") as queue:
        await broker.publish(
            "project-001",
            scan_id="scan-001",
            type="scan.started",
            message="Started",
            status="running",
        )
        event = await asyncio.wait_for(queue.get(), timeout=1.0)

    assert event["project_id"] == "project-001"
    assert event["scan_id"] == "scan-001"
    assert event["type"] == "scan.started"


@pytest.mark.asyncio
async def test_redis_backplane_filters_project_events_from_scan_subscriber() -> None:
    broker = ScanEventBroker(redis_cache=_FakeRedisCache())

    async with broker.subscribe("project-001", scan_id="scan-001") as queue:
        await broker.publish(
            "project-001",
            type="scan.info",
            message="Project-level notice",
        )

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.2)


@pytest.mark.asyncio
async def test_redis_backplane_reuses_one_subscription_per_project() -> None:
    redis_cache = _FakeRedisCache()
    broker = ScanEventBroker(redis_cache=redis_cache)

    async with broker.subscribe("project-001") as first_queue:
        async with broker.subscribe("project-001") as second_queue:
            await broker.publish(
                "project-001",
                scan_id="scan-001",
                type="scan.started",
                message="Started",
            )
            first_event = await asyncio.wait_for(first_queue.get(), timeout=1.0)
            second_event = await asyncio.wait_for(second_queue.get(), timeout=1.0)

    assert len(redis_cache._pubsubs) == 1
    assert first_event["type"] == "scan.started"
    assert second_event["type"] == "scan.started"


@pytest.mark.asyncio
async def test_redis_backplane_rejects_mismatched_project_payloads() -> None:
    redis_cache = _FakeRedisCache()
    broker = ScanEventBroker(redis_cache=redis_cache)

    async with broker.subscribe("project-001") as queue:
        pubsub = redis_cache._pubsubs[0]
        await pubsub.messages.put(
            {
                "data": json.dumps(
                    {
                        "id": "bad-event",
                        "type": "scan.info",
                        "message": "Wrong project",
                        "project_id": "project-999",
                        "scan_id": None,
                        "level": "info",
                        "phase": None,
                        "status": None,
                        "items_processed": None,
                        "timestamp": "2026-05-14T23:00:00Z",
                        "details": {},
                    }
                )
            }
        )

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.2)


@pytest.mark.asyncio
async def test_redis_backplane_recovers_after_listener_failure() -> None:
    redis_cache = _FakeRedisCache()
    broker = ScanEventBroker(redis_cache=redis_cache)

    async with broker.subscribe("project-001") as queue:
        pubsub = redis_cache._pubsubs[0]
        pubsub.raise_on_get = True
        event = await asyncio.wait_for(queue.get(), timeout=1.0)

    assert event["type"] == "stream.error"
    assert "Redis connection" in event["message"]

    async with broker.subscribe("project-001") as queue:
        await broker.publish(
            "project-001",
            type="scan.info",
            message="Recovered",
        )
        recovered_event = await asyncio.wait_for(queue.get(), timeout=1.0)

    assert recovered_event["message"] == "Recovered"
    assert len(redis_cache._pubsubs) == 2