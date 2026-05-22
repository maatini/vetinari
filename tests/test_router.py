"""Tests for LLMRouter with mocked litellm."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from expert_advisor.experts.prompts import Expert
from expert_advisor.routers.llm_router import (
    ExpertAdviceResponse,
    LLMRouter,
    RateLimiter,
    TTLCache,
    get_router,
)

# ── Test TTLCache ────────────────────────────────────────────────────────────


class TestTTLCache:
    """Tests for TTLCache."""

    def test_set_and_get(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        cache.set("prompt1", value="response1")
        assert cache.get("prompt1") == "response1"

    def test_miss(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        assert cache.get("unknown") is None

    def test_different_prompt_combos(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        cache.set("p1", value="r1")
        cache.set("p2", value="r2")
        cache.set("p3", value="r3")
        assert cache.get("p1") == "r1"
        assert cache.get("p2") == "r2"
        assert cache.get("p3") == "r3"

    def test_lru_eviction(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=3)
        cache.set("p1", value="r1")
        cache.set("p2", value="r2")
        cache.set("p3", value="r3")
        cache.set("p4", value="r4")  # Should evict p1
        assert cache.get("p1") is None
        assert cache.get("p4") == "r4"

    def test_clear(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        cache.set("p1", value="r1")
        cache.clear()
        assert cache.get("p1") is None

    def test_expired(self) -> None:
        cache = TTLCache(ttl_seconds=0, max_entries=10)
        cache.set("p1", value="r1")
        assert cache.get("p1") is None


# ── Test RateLimiter ─────────────────────────────────────────────────────────


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_allows_within_limit(self) -> None:
        rl = RateLimiter(window_seconds=60, max_requests=5)
        for _ in range(5):
            assert rl.check("model1") is True
            rl.record("model1")

    def test_blocks_over_limit(self) -> None:
        rl = RateLimiter(window_seconds=60, max_requests=2)
        rl.record("model1")
        rl.record("model1")
        assert rl.check("model1") is False

    def test_separate_per_model(self) -> None:
        rl = RateLimiter(window_seconds=60, max_requests=2)
        rl.record("model1")
        rl.record("model1")
        assert rl.check("model1") is False
        assert rl.check("model2") is True


# ── Test ExpertAdviceResponse ────────────────────────────────────────────────


class TestExpertAdviceResponse:
    """Tests for ExpertAdviceResponse."""

    def test_success_response(self) -> None:
        from expert_advisor.utils.cost_tracker import UsageInfo
        resp = ExpertAdviceResponse(
            expert_id="architect",
            expert_name="Architect",
            model_used="gpt-4o-mini",
            content="Hello",
            usage=UsageInfo(model="gpt-4o-mini"),
        )
        assert resp.success is True

    def test_error_response(self) -> None:
        from expert_advisor.utils.cost_tracker import UsageInfo
        resp = ExpertAdviceResponse(
            expert_id="architect",
            expert_name="Architect",
            model_used="gpt-4o-mini",
            content="",
            usage=UsageInfo(model="gpt-4o-mini", success=False),
            error="Something went wrong",
        )
        assert resp.success is False
        assert resp.error == "Something went wrong"


# ── Test LLMRouter consult (happy path with mock) ────────────────────────────


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
    def mock_litellm_completion(self):
        """Mock litellm.acompletion to return a fake response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response content"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            with patch("litellm.completion_cost", return_value=0.001):
                yield mock

    @pytest.mark.asyncio
    async def test_consult_success(self, expert: Expert, mock_litellm_completion) -> None:
        """Consult should return a successful response."""
        router = LLMRouter()
        response = await router.consult(expert, "What is architecture?")

        assert response.success is True
        assert response.content == "Test response content"
        assert response.expert_id == "test-expert"
        assert isinstance(response.model_used, str) and len(response.model_used) > 0
        assert response.error is None
        assert response.usage.total_tokens == 150
        assert response.usage.cost_usd == 0.001

    @pytest.mark.asyncio
    async def test_consult_cache_hit(self, expert: Expert, mock_litellm_completion) -> None:
        """Second call with same prompt should hit cache (no litellm call)."""
        router = LLMRouter()
        # First call - populates cache
        await router.consult(expert, "What is architecture?")
        call_count = mock_litellm_completion.call_count

        # Second call - should hit cache
        await router.consult(expert, "What is architecture?")
        assert mock_litellm_completion.call_count == call_count  # No additional call

    @pytest.mark.asyncio
    async def test_consult_fallback_on_error(self, expert: Expert) -> None:
        """When primary model fails, should fall back to next available."""
        router = LLMRouter()

        # Make all 6 models fail
        call_count = [0]

        async def mock_fail_all(**kwargs):
            call_count[0] += 1
            raise Exception(f"Error {call_count[0]}")

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = mock_fail_all
            with patch("litellm.completion_cost", return_value=0.0):
                response = await router.consult(expert, "Test")

        assert response.success is False
        assert response.error is not None
        assert call_count[0] == 6  # All 6 models tried (1 selected + 5 fallback)

    @pytest.mark.asyncio
    async def test_consult_all_models_fail(self, expert: Expert) -> None:
        """When all models fail, returns error response."""
        router = LLMRouter()

        async def mock_fail(**kwargs):
            raise Exception("All models down")

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_fail
            response = await router.consult(expert, "Test")

        assert response.success is False
        assert response.error is not None


# ── Test LLMRouter consult_multiple ──────────────────────────────────────────


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
        """consult_multiple should run in parallel and return all results."""
        router = LLMRouter()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response from expert"
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


# ── Test get_router ──────────────────────────────────────────────────────────


class TestGetRouter:
    """Tests for get_router singleton."""

    def test_singleton(self) -> None:
        r1 = get_router()
        r2 = get_router()
        assert r1 is r2
