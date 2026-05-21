from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with structured fields for the global exception handler."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "internal_error",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class CosmosOperationError(AppError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="cosmos_error", **kwargs)


class ScanError(AppError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="scan_error", **kwargs)


class PipelineError(AppError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="pipeline_error", **kwargs)
