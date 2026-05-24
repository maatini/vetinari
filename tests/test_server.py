"""Tests for MCP server tools (error paths + JSON formatting at tool boundary)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

# ── Test list_experts ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_experts_returns_all():
    from vetinari.server import list_experts

    result = json.loads(await list_experts())
    assert len(result) == 4
    assert {e["id"] for e in result} == {"architect", "reviewer", "security", "python"}


@pytest.mark.asyncio
async def test_list_experts_search():
    from vetinari.server import list_experts

    result = json.loads(await list_experts(query="security"))
    assert len(result) == 1
    assert result[0]["id"] == "security"


# ── Test get_expert_prompt ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_expert_prompt_success():
    from vetinari.server import get_expert_prompt

    result = json.loads(await get_expert_prompt(expert_id="python"))
    assert result["expert_id"] == "python"
    assert result["expert_name"] == "Python Expert"
    assert len(result["prompt"]) > 50


@pytest.mark.asyncio
async def test_get_expert_prompt_unknown():
    from vetinari.server import get_expert_prompt

    result = json.loads(await get_expert_prompt(expert_id="nonexistent"))
    assert "error" in result
    assert "available_ids" in result


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
    mock_resp.error_category = None

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
        resp.error_category = None
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
    assert result["partial_success"] is False
    assert result["succeeded_count"] == 2
    assert result["failed_count"] == 0
    assert len(result["responses"]) == 2
    assert result["responses"][0]["expert_id"] == "architect"
    assert result["responses"][1]["expert_id"] == "security"


@pytest.mark.asyncio
async def test_consult_multiple_partial_success():
    """consult_multiple_experts should report partial_success when some experts fail."""
    from vetinari.llm import UsageInfo
    from vetinari.server import consult_multiple_experts, router

    ok = AsyncMock()
    ok.success = True
    ok.expert_id = "architect"
    ok.expert_name = "Software Architect"
    ok.model_used = "gpt-4o-mini"
    ok.content = "Advice"
    ok.usage = UsageInfo(model="gpt-4o-mini")
    ok.fallback_used = False
    ok.retrieval_time_ms = 50.0
    ok.error = None
    ok.error_type = None
    ok.error_category = None

    failed = AsyncMock()
    failed.success = False
    failed.expert_id = "security"
    failed.expert_name = "Security Engineer"
    failed.model_used = "gpt-4o-mini"
    failed.content = ""
    failed.usage = UsageInfo(model="gpt-4o-mini")
    failed.fallback_used = True
    failed.retrieval_time_ms = 120.0
    failed.error = "Rate limit exceeded"
    failed.error_type = "RateLimitError"
    failed.error_category = "rate_limit"

    with patch.object(router, "consult_multiple", new_callable=AsyncMock) as mock_multi:
        mock_multi.return_value = [ok, failed]
        result_json = await consult_multiple_experts(
            expert_ids=["architect", "security"],
            query="How to secure a system?",
        )

    result = json.loads(result_json)
    assert result["success"] is False
    assert result["partial_success"] is True
    assert result["succeeded_count"] == 1
    assert result["failed_count"] == 1


@pytest.mark.asyncio
async def test_consult_multiple_all_failed():
    """consult_multiple_experts should report success=false when every expert fails."""
    from vetinari.llm import UsageInfo
    from vetinari.server import consult_multiple_experts, router

    def make_failed(eid: str, name: str):
        resp = AsyncMock()
        resp.success = False
        resp.expert_id = eid
        resp.expert_name = name
        resp.model_used = "gpt-4o-mini"
        resp.content = ""
        resp.usage = UsageInfo(model="gpt-4o-mini")
        resp.fallback_used = True
        resp.retrieval_time_ms = 100.0
        resp.error = "All models failed"
        resp.error_type = "Exception"
        resp.error_category = "unknown"
        return resp

    with patch.object(router, "consult_multiple", new_callable=AsyncMock) as mock_multi:
        mock_multi.return_value = [
            make_failed("architect", "Software Architect"),
            make_failed("security", "Security Engineer"),
        ]
        result_json = await consult_multiple_experts(
            expert_ids=["architect", "security"],
            query="Hello",
        )

    result = json.loads(result_json)
    assert result["success"] is False
    assert result["partial_success"] is False
    assert result["succeeded_count"] == 0
    assert result["failed_count"] == 2


@pytest.mark.asyncio
async def test_consult_expert_rejects_empty_query():
    from vetinari.server import consult_expert

    result = json.loads(await consult_expert(expert_id="architect", query="   "))
    assert result["success"] is False
    assert "empty" in result["error"].lower()


@pytest.mark.asyncio
async def test_consult_expert_rejects_oversized_query(monkeypatch: pytest.MonkeyPatch):
    from vetinari import config
    from vetinari.server import consult_expert

    monkeypatch.setattr(config.settings, "max_query_chars", 10)
    result = json.loads(await consult_expert(expert_id="architect", query="x" * 11))
    assert result["success"] is False
    assert "maximum length" in result["error"]


@pytest.mark.asyncio
async def test_consult_expert_rejects_excessive_max_tokens(monkeypatch: pytest.MonkeyPatch):
    from vetinari import config
    from vetinari.server import consult_expert

    monkeypatch.setattr(config.settings, "max_output_tokens", 100)
    result = json.loads(await consult_expert(expert_id="architect", query="Hi", max_tokens=101))
    assert result["success"] is False
    assert "max_tokens" in result["error"]


@pytest.mark.asyncio
async def test_consult_multiple_rejects_empty_expert_ids():
    from vetinari.server import consult_multiple_experts

    result = json.loads(await consult_multiple_experts(expert_ids=[], query="Hello"))
    assert result["success"] is False
    assert "expert_id" in result["error"].lower()


@pytest.mark.asyncio
async def test_consult_multiple_rejects_too_many_expert_ids(monkeypatch: pytest.MonkeyPatch):
    from vetinari import config
    from vetinari.server import consult_multiple_experts

    monkeypatch.setattr(config.settings, "max_experts_per_request", 2)
    result = json.loads(
        await consult_multiple_experts(
            expert_ids=["architect", "reviewer", "security"],
            query="Hello",
        ),
    )
    assert result["success"] is False
    assert "Too many expert_ids" in result["error"]


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


