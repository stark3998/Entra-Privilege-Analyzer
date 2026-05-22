# backend/app/config.py
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    local_mode: bool = False
    debug_mode: bool = False
    backend_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    cors_origin_regex: str = (
        "^https://(ca-entraperm-frontend-[a-z0-9-]+\\.[a-z0-9-]+\\.[a-z]+\\.azurecontainerapps\\.io|[a-z0-9-]+\\.jatinmadan\\.com)$"
    )

    # Entra ID
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # Microsoft Graph API version ("beta" for latest features, "v1.0" for GA stability)
    graph_api_version: str = "beta"

    # Cosmos DB
    cosmos_endpoint: str = "https://localhost:8081"
    cosmos_key: str = ""
    cosmos_master_database: str = "entra-master"

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
    azure_openai_api_version: str = "2024-02-01"

    # Encryption (base64-encoded 32-byte key for AES-256-GCM)
    encryption_key: str = ""

    # Scan Function App
    scan_function_app_url: str = ""
    scan_function_key: str = ""

    # Log Analytics workspace ID for querying Function App logs
    log_analytics_workspace_id: str = ""

    # PIM Privileged Session Tracking
    pim_session_enabled: bool = True
    pim_session_poll_interval_minutes: int = 15
    pim_session_backfill_days: int = 30
    pim_session_business_hours_start: int = 7
    pim_session_business_hours_end: int = 19

    # Observability
    log_format: str = "text"
    otel_service_name: str = "entra-permissions-analyzer"

    # App Insights
    applicationinsights_connection_string: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
