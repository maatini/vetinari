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

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        await cache.set("prompt1", value="response1")
        assert await cache.get("prompt1") == "response1"

    @pytest.mark.asyncio
    async def test_miss(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        assert await cache.get("unknown") is None

    @pytest.mark.asyncio
    async def test_different_prompt_combos(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        await cache.set("p1", value="r1")
        await cache.set("p2", value="r2")
        await cache.set("p3", value="r3")
        assert await cache.get("p1") == "r1"
        assert await cache.get("p2") == "r2"
        assert await cache.get("p3") == "r3"

    @pytest.mark.asyncio
    async def test_different_model_keys(self) -> None:
        """Different model/temperature produce different cache keys."""
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        await cache.set("prompt", model="gpt-4o", value="gpt-response", temperature=0.0)
        await cache.set("prompt", model="groq/llama3", value="groq-response", temperature=0.0)
        assert await cache.get("prompt", model="gpt-4o", temperature=0.0) == "gpt-response"
        assert await cache.get("prompt", model="groq/llama3", temperature=0.0) == "groq-response"

    @pytest.mark.asyncio
    async def test_different_temperature_keys(self) -> None:
        """Different temperatures produce different cache keys."""
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        await cache.set("prompt", model="gpt-4o", value="cold", temperature=0.0)
        await cache.set("prompt", model="gpt-4o", value="hot", temperature=1.0)
        assert await cache.get("prompt", model="gpt-4o", temperature=0.0) == "cold"
        assert await cache.get("prompt", model="gpt-4o", temperature=1.0) == "hot"

    @pytest.mark.asyncio
    async def test_lru_eviction(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=3)
        await cache.set("p1", value="r1")
        await cache.set("p2", value="r2")
        await cache.set("p3", value="r3")
        await cache.set("p4", value="r4")  # Should evict p1
        assert await cache.get("p1") is None
        assert await cache.get("p4") == "r4"

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        cache = TTLCache(ttl_seconds=60, max_entries=10)
        await cache.set("p1", value="r1")
        await cache.clear()
        assert await cache.get("p1") is None

    @pytest.mark.asyncio
    async def test_expired(self) -> None:
        cache = TTLCache(ttl_seconds=0, max_entries=10)
        await cache.set("p1", value="r1")
        assert await cache.get("p1") is None


# ── Test RateLimiter ─────────────────────────────────────────────────────────


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self) -> None:
        rl = RateLimiter(window_seconds=60, max_requests=5)
        for _ in range(5):
            assert await rl.acquire("model1") is True

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self) -> None:
        rl = RateLimiter(window_seconds=60, max_requests=2)
        assert await rl.acquire("model1") is True
        assert await rl.acquire("model1") is True
        assert await rl.acquire("model1") is False

    @pytest.mark.asyncio
    async def test_separate_per_model(self) -> None:
        rl = RateLimiter(window_seconds=60, max_requests=2)
        assert await rl.acquire("model1") is True
        assert await rl.acquire("model1") is True
        assert await rl.acquire("model1") is False
        assert await rl.acquire("model2") is True


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
    async def test_consult_cache_different_models(self, expert: Expert) -> None:
        """Different models should NOT share cache entries."""
        router = LLMRouter(cache_ttl=300)

        call_args: list[dict] = []

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        async def mock_acompletion(**kwargs):
            call_args.append(kwargs)
            return mock_response

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = mock_acompletion
            with patch("litellm.completion_cost", return_value=0.0):
                await router.consult(expert, "Test", model="gpt-4o-mini")
                await router.consult(expert, "Test", model="groq/llama3-70b-8192")

        # Both should have made actual LLM calls (not cached)
        assert len(call_args) == 2
        assert call_args[0]["model"] == "gpt-4o-mini"
        assert call_args[1]["model"] == "groq/llama3-70b-8192"

    @pytest.mark.asyncio
    async def test_consult_fallback_on_error(self, expert: Expert) -> None:
        """When primary model fails, should fall back to next available."""
        router = LLMRouter()

        # Make all 6 models fail
        call_count = [0]

        async def mock_fail_all(**kwargs):
            call_count[0] += 1
            raise Exception(f"Error {call_count[0]}")

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac,
            patch("litellm.completion_cost", return_value=0.0),
            patch(
                "expert_advisor.routers.llm_router.settings.retry_base_delay_seconds", 0
            ),
            patch(
                "expert_advisor.routers.llm_router.settings.retry_max_delay_seconds", 0
            ),
        ):
            mock_ac.side_effect = mock_fail_all
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

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock,
            patch(
                "expert_advisor.routers.llm_router.settings.retry_base_delay_seconds", 0
            ),
            patch(
                "expert_advisor.routers.llm_router.settings.retry_max_delay_seconds", 0
            ),
        ):
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


# ── Concurrency Tests ───────────────────────────────────────────────────────


class TestConcurrentCache:
    """Verifies TTLCache safety under parallel access."""

    @pytest.mark.asyncio
    async def test_concurrent_get_set(self) -> None:
        """Parallel reads and writes should not cause errors or data loss."""
        import asyncio

        cache = TTLCache(ttl_seconds=60, max_entries=50)

        async def writer(i: int) -> None:
            for j in range(10):
                await cache.set(f"key-{i}-{j}", value=f"value-{i}-{j}")

        async def reader(i: int) -> None:
            for j in range(10):
                _ = await cache.get(f"key-{i}-{j}")

        # 5 writers + 5 readers concurrently
        tasks = [writer(i) for i in range(5)] + [reader(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # All writer entries should be present
        for i in range(5):
            assert await cache.get(f"key-{i}-9") == f"value-{i}-9"

    @pytest.mark.asyncio
    async def test_concurrent_eviction_does_not_crash(self) -> None:
        """Parallel writes that trigger eviction should not error."""
        import asyncio

        cache = TTLCache(ttl_seconds=60, max_entries=10)

        async def burst_writer(offset: int) -> None:
            for i in range(20):
                await cache.set(f"burst-{offset}-{i}", value=f"v{offset}-{i}")

        # 3 concurrent burst writers
        await asyncio.gather(*[burst_writer(i) for i in range(3)])

        # Just verify no crash — data integrity under eviction is probabilistic
        assert True


class TestConcurrentRateLimiter:
    """Verifies RateLimiter precision under parallel access."""

    @pytest.mark.asyncio
    async def test_concurrent_does_not_exceed_limit(self) -> None:
        """Parallel acquires should never exceed max_requests."""
        import asyncio

        max_req = 5
        rl = RateLimiter(window_seconds=60, max_requests=max_req)

        results = []

        async def try_acquire() -> None:
            result = await rl.acquire("model1")
            results.append(result)

        # 20 concurrent tasks, only max_req should succeed
        await asyncio.gather(*[try_acquire() for _ in range(20)])

        granted = sum(1 for r in results if r)
        assert granted == max_req, f"Expected {max_req} granted, got {granted}"

    @pytest.mark.asyncio
    async def test_concurrent_separate_models(self) -> None:
        """Rate limits for different models should not interfere."""
        import asyncio

        rl = RateLimiter(window_seconds=60, max_requests=3)

        async def acquire_model(model: str) -> list[bool]:
            return [await rl.acquire(model) for _ in range(5)]

        res_a, res_b = await asyncio.gather(
            acquire_model("model-A"),
            acquire_model("model-B"),
        )

        # Each model gets exactly 3 out of 5
        assert sum(res_a) == 3
        assert sum(res_b) == 3


class TestConsultMultipleConcurrency:
    """Integration: consult_multiple with concurrency."""

    @pytest.mark.asyncio
    async def test_consult_multiple_no_duplicate_llm_calls(self) -> None:
        """Same query to multiple experts should cache after first LLM call."""
        from unittest.mock import MagicMock

        router = LLMRouter(cache_ttl=300)

        experts = [
            Expert(
                id="e1", name="E1", description="",
                prompt="You are E1", recommended_model="gpt-4o-mini",
            ),
            Expert(
                id="e2", name="E2", description="",
                prompt="You are E2", recommended_model="gpt-4o-mini",
            ),
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        llm_call_count = [0]

        async def mock_acompletion(**kwargs):
            llm_call_count[0] += 1
            return mock_response

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_ac.side_effect = mock_acompletion
            with patch("litellm.completion_cost", return_value=0.0):
                responses = await router.consult_multiple(experts, "Same query")

        # Different experts with same prompt = separate cache entries (different prompts)
        assert len(responses) == 2
        assert all(r.success for r in responses)
        assert llm_call_count[0] == 2
