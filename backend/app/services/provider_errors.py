"""Typed failures and results for deterministic access providers."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProviderFailureCategory(StrEnum):
    """Stable failure categories used by orchestration retry policy."""

    AUTHORIZATION = "authorization"
    THROTTLED = "throttled"
    TRANSIENT = "transient"
    CONFLICT = "conflict"
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class ProviderOperationResult(BaseModel):
    """Provider-neutral result persisted after postcondition verification."""

    provider: str
    operation_id: str | None = None
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ProviderOperationError(RuntimeError):
    """A safe, classified provider failure suitable for workflow decisions."""

    def __init__(
        self,
        category: ProviderFailureCategory,
        message: str,
        *,
        provider: str,
        retryable: bool,
        status_code: int | None = None,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id

    @classmethod
    def from_http_status(
        cls,
        status_code: int,
        message: str,
        *,
        provider: str,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> ProviderOperationError:
        """Classify common Graph and ARM HTTP failures consistently."""
        if status_code in (401, 403):
            category = ProviderFailureCategory.AUTHORIZATION
            retryable = False
        elif status_code == 404:
            category = ProviderFailureCategory.NOT_FOUND
            retryable = False
        elif status_code == 409:
            category = ProviderFailureCategory.CONFLICT
            retryable = False
        elif status_code == 429:
            category = ProviderFailureCategory.THROTTLED
            retryable = True
        elif 400 <= status_code < 500:
            category = ProviderFailureCategory.INVALID_REQUEST
            retryable = False
        elif status_code >= 500:
            category = ProviderFailureCategory.TRANSIENT
            retryable = True
        else:
            category = ProviderFailureCategory.UNKNOWN
            retryable = False
        return cls(
            category,
            message,
            provider=provider,
            retryable=retryable,
            status_code=status_code,
            error_code=error_code,
            request_id=request_id,
        )
