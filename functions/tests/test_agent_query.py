from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FUNCTIONS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FUNCTIONS_ROOT))

from agents.models import (  # noqa: E402
    AgentDescriptor,
    AgentQueryResponse,
    QueryTrace,
    StructuredAnswer,
    StructuredAnswerFinding,
)
from blueprints.agent_workflows_bp import (  # noqa: E402
    _query_agent_impl,
    query_agent,
    validate_agent_query_payload,
)


def _request_payload() -> dict:
    return {
        "project_id": "project-1",
        "tenant_id": "tenant-1",
        "user_id": "user-1",
        "query": "Why is this identity high risk?",
        "scope": {
            "identity_id": "User-user-1",
            "max_results": 5,
        },
        "correlation_id": "corr-123",
    }


def _response_model() -> AgentQueryResponse:
    return AgentQueryResponse(
        answer="User One has standing admin access.\n- Permanent admin role: Global Administrator remains assigned.",
        structured_answer=StructuredAnswer(
            summary="User One has standing admin access.",
            findings=[
                StructuredAnswerFinding(
                    title="Permanent admin role",
                    summary="Global Administrator remains assigned.",
                    evidence_ids=["identity:User-user-1"],
                )
            ],
            next_steps=["Review whether User Administrator is sufficient."],
            limitations=[],
        ),
        citations=[
            {
                "evidence_id": "identity:User-user-1",
                "label": "User One",
                "source": "identity_profiles",
                "target_type": "identity_profile",
                "target_id": "User-user-1",
            }
        ],
        evidence_ids=["identity:User-user-1"],
        agent=AgentDescriptor(
            name="scoped-copilot-query",
            role="investigator",
            version="2026-09-15.2",
            prompt_name="entra.scoped_copilot_query",
            prompt_version="2026-09-15.2",
            model="gpt-4o-mini",
            provider="foundry",
        ),
        version="2026-09-15.2",
        correlation_id="corr-123",
        trace=QueryTrace(
            correlation_id="corr-123",
            trace_id="abc",
            span_id="def",
        ),
    )


def test_validate_agent_query_payload_rejects_nested_secrets() -> None:
    payload = _request_payload()
    payload["scope"] = {
        "identity_id": "User-user-1",
        "filters": [{"access_token": "x"}],
    }

    error = validate_agent_query_payload(payload)

    assert error is not None
    assert "Secret-bearing fields" in error


@pytest.mark.asyncio
async def test_query_agent_impl_returns_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_run(_request):
        return _response_model()

    monkeypatch.setattr(
        "blueprints.agent_workflows_bp._QUERY_RUNNER",
        type("Runner", (), {"run": staticmethod(_fake_run)})(),
    )

    response = await _query_agent_impl(_request_payload())

    assert response.answer.startswith("User One")
    assert response.citations[0].evidence_id == "identity:User-user-1"
    assert response.agent.name == "scoped-copilot-query"
    assert response.trace.correlation_id == "corr-123"


@pytest.mark.asyncio
async def test_query_agent_http_endpoint_returns_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_impl(_body: dict) -> AgentQueryResponse:
        return _response_model()

    monkeypatch.setattr("blueprints.agent_workflows_bp._query_agent_impl", _fake_impl)

    req = MagicMock()
    req.get_json.return_value = _request_payload()

    response = await query_agent(req)
    payload = json.loads(response.get_body().decode())

    assert response.status_code == 200
    assert payload["answer"].startswith("User One")
    assert payload["agent"]["version"] == "2026-09-15.2"
    assert payload["trace"]["correlation_id"] == "corr-123"


@pytest.mark.asyncio
async def test_query_agent_http_endpoint_rejects_invalid_body() -> None:
    req = MagicMock()
    req.get_json.return_value = {"project_id": "project-1"}

    response = await query_agent(req)
    payload = json.loads(response.get_body().decode())

    assert response.status_code == 400
    assert "error" in payload
