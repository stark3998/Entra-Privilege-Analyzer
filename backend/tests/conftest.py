# backend/tests/conftest.py
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings, get_settings


def _test_settings() -> Settings:
    """Settings override for tests — LOCAL_MODE on, no real services."""
    return Settings(
        local_mode=True,
        cosmos_endpoint="",
        cosmos_key="",
        redis_host="localhost",
        redis_password="",
        applicationinsights_connection_string="",
    )


@pytest.fixture()
def settings() -> Settings:
    """Provide test settings."""
    return _test_settings()


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an httpx AsyncClient wired to the FastAPI app."""
    from app.main import create_app

    # Override the settings dependency so LOCAL_MODE is always on
    test_app = create_app()
    test_app.dependency_overrides[get_settings] = _test_settings

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
