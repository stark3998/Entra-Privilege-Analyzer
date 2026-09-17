"""Explicit failures for durable agent workflow execution."""

from __future__ import annotations


class AgentWorkflowError(RuntimeError):
    """Base error for Functions-hosted agent workflows."""


class AgentWorkflowConfigurationError(AgentWorkflowError):
    """Raised when required agent workflow configuration is missing or invalid."""


class AgentToolPolicyError(AgentWorkflowError):
    """Raised when a role requests a tool outside its read-only allowlist."""


class AgentExecutionError(AgentWorkflowError):
    """Raised when the underlying model response is missing or invalid."""
