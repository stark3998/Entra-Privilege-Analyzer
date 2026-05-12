# backend/app/models/export.py
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ExportFormat(StrEnum):
    """Supported IaC export formats."""

    TERRAFORM = "terraform"
    BICEP = "bicep"
    ARM = "arm"


class ExportResult(BaseModel):
    """Result of an IaC export for a single identity."""

    format: ExportFormat
    identity_id: str
    content: str
    filename: str
