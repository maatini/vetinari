"""Tests for MCP server tools."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

# ── Test list_experts ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_experts():
    """list_experts should return all 11 experts."""
    from expert_advisor.server import list_experts

    result_json = await list_experts()
    result = json.loads(result_json)
    assert isinstance(result, list)
    assert len(result) == 11
    # Check structure
    first = result[0]
    assert "id" in first
    assert "name" in first
    assert "description" in first
    assert "tags" in first
    assert "recommended_model" in first


@pytest.mark.asyncio
async def test_list_experts_with_query():
    """list_experts with query should filter results."""
    from expert_advisor.server import list_experts

    result_json = await list_experts(query="python")
    result = json.loads(result_json)
    assert len(result) == 1
    assert result[0]["id"] == "python-expert"


# ── Test search_experts ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_experts():
    """search_experts should find matching experts."""
    from expert_advisor.server import search_experts

    result_json = await search_experts("security")
    result = json.loads(result_json)
    assert len(result) >= 1
    assert any(e["id"] == "security" for e in result)


# ── Test get_expert_prompt ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_expert_prompt():
    """get_expert_prompt should return the prompt for a valid expert."""
    from expert_advisor.server import get_expert_prompt

    result_json = await get_expert_prompt("architect")
    result = json.loads(result_json)
    assert result["expert_id"] == "architect"
    assert "Software Architect" in result["expert_name"]
    assert len(result["prompt"]) > 100


@pytest.mark.asyncio
async def test_get_expert_prompt_unknown():
    """get_expert_prompt should return error for unknown expert."""
    from expert_advisor.server import get_expert_prompt

    result_json = await get_expert_prompt("nonexistent")
    result = json.loads(result_json)
    assert "error" in result
    assert "available_ids" in result


# ── Test consult_expert ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consult_expert_success():
    """consult_expert should return advice from the expert."""
    from expert_advisor.server import consult_expert, router

    # Mock the router's consult method
    mock_resp = AsyncMock()
    mock_resp.success = True
    mock_resp.expert_id = "architect"
    mock_resp.expert_name = "Software Architect"
    mock_resp.model_used = "gpt-4o-mini"
    mock_resp.content = "Test architecture advice"
    from expert_advisor.utils.cost_tracker import UsageInfo
    mock_resp.usage = UsageInfo(prompt_tokens=100, completion_tokens=50, model="gpt-4o-mini")
    mock_resp.fallback_used = False
    mock_resp.retrieval_time_ms = 123.4
    mock_resp.error = None

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
    from expert_advisor.server import consult_expert

    result_json = await consult_expert(expert_id="nonexistent", query="Hello")
    result = json.loads(result_json)
    assert result["success"] is False
    assert "Unknown expert" in result["error"]


# ── Test consult_multiple_experts ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consult_multiple_experts():
    """consult_multiple_experts should query multiple experts."""
    from expert_advisor.server import consult_multiple_experts, router
    from expert_advisor.utils.cost_tracker import UsageInfo

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
        return resp

    mock_responses = [
        make_resp("architect", "Software Architect"),
        make_resp("security", "Cybersecurity Analyst"),
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
    from expert_advisor.server import consult_multiple_experts

    result_json = await consult_multiple_experts(
        expert_ids=["nonexistent1", "nonexistent2"],
        query="Hello",
    )
    result = json.loads(result_json)
    assert result["success"] is False
    assert len(result["unknown_ids"]) == 2


# ── Test cost_summary ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cost_summary():
    """cost_summary should return cost stats."""
    from expert_advisor.server import cost_summary

    result_json = await cost_summary()
    result = json.loads(result_json)
    assert "total_cost_usd" in result
    assert "total_tokens" in result
    assert "total_calls" in result
