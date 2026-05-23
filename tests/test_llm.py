"""Tests for llm.py (LLMRouter, SimpleCache, UsageInfo, response objects)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from expert_advisor.experts import Expert
from expert_advisor.llm import (
    ExpertAdviceResponse,
    LLMRouter,
    SimpleCache,
    UsageInfo,
)


class TestUsageInfo:
    """Tests for UsageInfo dataclass."""

    def test_defaults(self) -> None:
        u = UsageInfo()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.cost_usd == 0.0
        assert u.model == "unknown"


# ── SimpleCache ──────────────────────────────────────────────────────────────


class TestSimpleCache:
    """Tests for SimpleCache."""

    def test_set_and_get(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        cache.set("prompt1", value="response1")
        assert cache.get("prompt1") == "response1"

    def test_miss(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        assert cache.get("unknown") is None

    def test_different_model_keys(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        cache.set("prompt", model="gpt-4o", value="gpt-response", temperature=0.0)
        cache.set("prompt", model="groq/llama3", value="groq-response", temperature=0.0)
        assert cache.get("prompt", model="gpt-4o", temperature=0.0) == "gpt-response"
        assert cache.get("prompt", model="groq/llama3", temperature=0.0) == "groq-response"

    def test_different_temperature_keys(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        cache.set("prompt", model="gpt-4o", value="cold", temperature=0.0)
        cache.set("prompt", model="gpt-4o", value="hot", temperature=1.0)
        assert cache.get("prompt", model="gpt-4o", temperature=0.0) == "cold"
        assert cache.get("prompt", model="gpt-4o", temperature=1.0) == "hot"

    def test_max_entries_eviction(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=3)
        cache.set("p1", value="r1")
        cache.set("p2", value="r2")
        cache.set("p3", value="r3")
        cache.set("p4", value="r4")
        # Oldest entry (p1) should be evicted
        assert cache.get("p1") is None
        assert cache.get("p4") == "r4"

    def test_expired(self) -> None:
        cache = SimpleCache(ttl_seconds=0, max_entries=10)
        cache.set("p1", value="r1")
        assert cache.get("p1") is None


# ── ExpertAdviceResponse ─────────────────────────────────────────────────────


class TestExpertAdviceResponse:
    """Tests for ExpertAdviceResponse."""

    def test_success_response(self) -> None:
        resp = ExpertAdviceResponse(
            expert_id="architect",
            expert_name="Architect",
            model_used="gpt-4o-mini",
            content="Hello",
        )
        assert resp.success is True

    def test_error_response(self) -> None:
        resp = ExpertAdviceResponse(
            expert_id="architect",
            expert_name="Architect",
            model_used="gpt-4o-mini",
            content="",
            error="Something went wrong",
        )
        assert resp.success is False
        assert resp.error == "Something went wrong"


# ── LLMRouter.consult ────────────────────────────────────────────────────────


class TestLLMRouterConsult:
    """Tests for LLMRouter.consult with mocked litellm."""

    @pytest.fixture
    def expert(self) -> Expert:
        return Expert(
            id="test-expert",
            name="Test Expert",
            description="A test expert",
            prompt="You are a test expert.",
            recommended_model="gpt-4o-mini",
        )

    @pytest.fixture
    def mock_litellm(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response content"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.return_value = mock_response
            with patch("litellm.completion_cost", return_value=0.001):
                yield mock_ac

    @pytest.mark.asyncio
    async def test_consult_success(self, expert: Expert, mock_litellm) -> None:
        router = LLMRouter()
        response = await router.consult(expert, "What is architecture?")

        assert response.success is True
        assert response.content == "Test response content"
        assert response.expert_id == "test-expert"
        assert response.error is None
        assert response.usage.prompt_tokens == 100
        assert response.usage.completion_tokens == 50
        assert response.usage.cost_usd == 0.001

    @pytest.mark.asyncio
    async def test_consult_with_cache_enabled(self, expert: Expert, mock_litellm) -> None:
        """Second call with same prompt should hit cache."""
        router = LLMRouter(enable_cache=True)
        await router.consult(expert, "What is architecture?")
        call_count = mock_litellm.call_count
        await router.consult(expert, "What is architecture?")
        # No additional LLM call
        assert mock_litellm.call_count == call_count

    @pytest.mark.asyncio
    async def test_consult_no_cache_by_default(self, expert: Expert, mock_litellm) -> None:
        """Without cache enabled, every call hits LLM."""
        router = LLMRouter()
        await router.consult(expert, "What is architecture?")
        await router.consult(expert, "What is architecture?")
        assert mock_litellm.call_count == 2

    @pytest.mark.asyncio
    async def test_consult_fallback_on_error(self, expert: Expert) -> None:
        """When primary fails, should fall back to next model."""
        router = LLMRouter()
        call_count = [0]

        async def mock_fail_all(**kwargs):
            call_count[0] += 1
            raise Exception(f"Error {call_count[0]}")

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac,
            patch("litellm.completion_cost", return_value=0.0),
        ):
            mock_ac.side_effect = mock_fail_all
            response = await router.consult(expert, "Test")

        assert response.success is False
        assert response.error is not None
        # Tried all 3 default models
        assert call_count[0] == 3

    @pytest.mark.asyncio
    async def test_consult_all_models_fail(self, expert: Expert) -> None:
        router = LLMRouter()

        async def mock_fail(**kwargs):
            raise Exception("All models down")

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_fail
            response = await router.consult(expert, "Test")

        assert response.success is False
        assert response.error is not None


# ── LLMRouter.consult_multiple ───────────────────────────────────────────────


class TestLLMRouterConsultMultiple:
    """Tests for consult_multiple."""

    @pytest.fixture
    def experts(self) -> list[Expert]:
        return [
            Expert(id="e1", name="E1", description="D1", prompt="P1"),
            Expert(id="e2", name="E2", description="D2", prompt="P2"),
            Expert(id="e3", name="E3", description="D3", prompt="P3"),
        ]

    @pytest.mark.asyncio
    async def test_consult_multiple_parallel(self, experts: list[Expert]) -> None:
        router = LLMRouter()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch("litellm.completion_cost", return_value=0.0):
                responses = await router.consult_multiple(experts, "Test query")

        assert len(responses) == 3
        for r in responses:
            assert r.success is True
            assert r.expert_id in ("e1", "e2", "e3")
