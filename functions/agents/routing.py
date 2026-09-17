"""Model routing for Functions-hosted durable agent workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass

from agents.errors import AgentWorkflowConfigurationError
from agents.models import AgentRole, ModelRoute


@dataclass(frozen=True)
class _RouteDefaults:
    temperature: float
    max_tokens: int
    verbosity: str


_ROLE_DEFAULTS: dict[AgentRole, _RouteDefaults] = {
    AgentRole.INVESTIGATOR: _RouteDefaults(
        temperature=0.1, max_tokens=2200, verbosity="medium"
    ),
    AgentRole.RISK: _RouteDefaults(temperature=0.0, max_tokens=1800, verbosity="low"),
    AgentRole.PERSONA: _RouteDefaults(
        temperature=0.1, max_tokens=1800, verbosity="low"
    ),
    AgentRole.CRITIC: _RouteDefaults(temperature=0.0, max_tokens=1600, verbosity="low"),
    AgentRole.PLANNER: _RouteDefaults(
        temperature=0.1, max_tokens=2200, verbosity="medium"
    ),
    AgentRole.VERIFIER: _RouteDefaults(
        temperature=0.0, max_tokens=1600, verbosity="low"
    ),
}


class ModelRouter:
    """Resolve per-role model routes using explicit env overrides."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def resolve(self, role: AgentRole, override_model: str | None = None) -> ModelRoute:
        provider = (
            self._environ.get("AGENT_WORKFLOW_PROVIDER", "foundry").strip().lower()
        )
        if provider != "foundry":
            raise AgentWorkflowConfigurationError(
                f"Unsupported AGENT_WORKFLOW_PROVIDER '{provider}'. Only 'foundry' is supported."
            )

        model = (
            (override_model or "").strip()
            or self._environ.get(f"AGENT_WORKFLOW_MODEL_{role.name}", "").strip()
            or self._environ.get("AGENT_WORKFLOW_MODEL_DEFAULT", "").strip()
            or self._environ.get("FOUNDRY_MODEL", "").strip()
        )
        if not model:
            raise AgentWorkflowConfigurationError(
                f"No model configured for {role.value}. Set AGENT_WORKFLOW_MODEL_{role.name}, "
                "AGENT_WORKFLOW_MODEL_DEFAULT, or FOUNDRY_MODEL."
            )

        defaults = _ROLE_DEFAULTS[role]
        return ModelRoute(
            provider="foundry",
            model=model,
            temperature=defaults.temperature,
            max_tokens=defaults.max_tokens,
            verbosity=defaults.verbosity,
        )

    def resolve_query(self) -> ModelRoute:
        override = self._environ.get("AGENT_WORKFLOW_MODEL_QUERY", "").strip()
        return self.resolve(AgentRole.INVESTIGATOR, override_model=override or None)
