# backend/app/services/foundry.py
"""FoundryClient wrapper for Microsoft Foundry AI inference."""
from __future__ import annotations

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_foundry_client: FoundryClient | None = None


class FoundryClient:
    """Async wrapper around Azure AI Foundry chat completions endpoint."""

    def __init__(self, endpoint: str, key: str, model: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._key = key
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Call the Foundry chat completions endpoint and return the content string.

        Returns a fallback message on any failure rather than raising.
        """
        url = (
            f"{self._endpoint}/openai/deployments/{self._model}"
            f"/chat/completions?api-version=2024-02-01"
        )
        headers = {
            "api-key": self._key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                logger.info(
                    "foundry.usage model=%s prompt_tokens=%d completion_tokens=%d",
                    self._model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                import re as _re
                raw = str(data["choices"][0]["message"]["content"])
                clean = _re.sub(r"<[^>]+>", "", raw)
                return clean[:5000]
        except Exception as exc:
            logger.error(
                "Foundry completion failed: type=%s status=%s",
                type(exc).__name__,
                getattr(exc, "status_code", "N/A"),
            )
            return "AI narrative generation is temporarily unavailable. Please try again later."


def init_foundry_client(settings: Settings) -> FoundryClient | None:
    """Initialise the global FoundryClient singleton.

    Returns None if the endpoint or key is not configured.
    """
    global _foundry_client
    if not settings.azure_foundry_endpoint or not settings.azure_foundry_key:
        logger.warning("Foundry not configured — AI narratives disabled")
        return None

    _foundry_client = FoundryClient(
        endpoint=settings.azure_foundry_endpoint,
        key=settings.azure_foundry_key,
        model=settings.azure_foundry_model,
    )
    logger.info("FoundryClient initialised with model=%s", settings.azure_foundry_model)
    return _foundry_client


def get_foundry_client() -> FoundryClient | None:
    """Return the global FoundryClient instance, or None if not configured."""
    return _foundry_client
