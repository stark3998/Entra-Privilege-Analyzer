# backend/app/config.py
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    local_mode: bool = False
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # Entra ID
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # Cosmos DB
    cosmos_endpoint: str = "https://localhost:8081"
    cosmos_key: str = ""
    cosmos_database: str = "entra-analyzer"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_ssl: bool = False

    # Key Vault
    keyvault_url: str = ""

    # Foundry
    azure_foundry_endpoint: str = ""
    azure_foundry_key: str = ""
    azure_foundry_model: str = "gpt-4o"

    # App Insights
    applicationinsights_connection_string: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
