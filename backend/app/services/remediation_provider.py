"""Execution contract for deterministic remediation providers."""

from __future__ import annotations

from typing import Protocol

from app.models.remediation import RemediationAction
from app.services.provider_errors import ProviderOperationResult


class RemediationProvider(Protocol):
    """Executes one previously validated remediation action."""

    async def execute(
        self,
        action: RemediationAction,
        access_token: str,
    ) -> ProviderOperationResult: ...
