"""Tests for MCP server tools (error paths + JSON formatting at tool boundary)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

# ── Test consult_expert ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consult_expert_success():
    """consult_expert should return advice from the expert."""
    from vetinari.llm import UsageInfo
    from vetinari.server import consult_expert, router

    mock_resp = AsyncMock()
    mock_resp.success = True
    mock_resp.expert_id = "architect"
    mock_resp.expert_name = "Software Architect"
    mock_resp.model_used = "gpt-4o-mini"
    mock_resp.content = "Test architecture advice"
    mock_resp.usage = UsageInfo(prompt_tokens=100, completion_tokens=50, model="gpt-4o-mini")
    mock_resp.fallback_used = False
    mock_resp.retrieval_time_ms = 123.4
    mock_resp.error = None
    mock_resp.error_type = None

    with patch.object(router, "consult", new_callable=AsyncMock) as mock_consult:
        mock_consult.return_value = mock_resp
        result_json = await consult_expert(expert_id="architect", query="Design a system")

    result = json.loads(result_json)
    assert result["success"] is True
    assert result["expert_id"] == "architect"
    assert result["content"] == "Test architecture advice"


@pytest.mark.asyncio
async def test_consult_expert_unknown():
    """consult_expert should return error for unknown expert ID."""
    from vetinari.server import consult_expert

    result_json = await consult_expert(expert_id="nonexistent", query="Hello")
    result = json.loads(result_json)
    assert result["success"] is False
    assert "Unknown expert" in result["error"]


# ── Test consult_multiple_experts ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consult_multiple_experts():
    """consult_multiple_experts should query multiple experts."""
    from vetinari.llm import UsageInfo
    from vetinari.server import consult_multiple_experts, router

    def make_resp(eid, name):
        resp = AsyncMock()
        resp.success = True
        resp.expert_id = eid
        resp.expert_name = name
        resp.model_used = "gpt-4o-mini"
        resp.content = f"Advice from {name}"
        resp.usage = UsageInfo(model="gpt-4o-mini")
        resp.fallback_used = False
        resp.retrieval_time_ms = 50.0
        resp.error = None
        resp.error_type = None
        return resp

    mock_responses = [
        make_resp("architect", "Software Architect"),
        make_resp("security", "Security Engineer"),
    ]

    with patch.object(router, "consult_multiple", new_callable=AsyncMock) as mock_multi:
        mock_multi.return_value = mock_responses
        result_json = await consult_multiple_experts(
            expert_ids=["architect", "security"],
            query="How to secure a system?",
        )

    result = json.loads(result_json)
    assert result["success"] is True
    assert len(result["responses"]) == 2
    assert result["responses"][0]["expert_id"] == "architect"
    assert result["responses"][1]["expert_id"] == "security"


@pytest.mark.asyncio
async def test_consult_multiple_with_unknown_ids():
    """consult_multiple_experts should report unknown IDs."""
    from vetinari.server import consult_multiple_experts

    result_json = await consult_multiple_experts(
        expert_ids=["nonexistent1", "nonexistent2"],
        query="Hello",
    )
    result = json.loads(result_json)
    assert result["success"] is False
    assert len(result["unknown_ids"]) == 2


