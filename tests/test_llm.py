"""Tests for llm.py (LLMRouter, SimpleCache, UsageInfo, response objects)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# For error classification tests (Phase 1)
from litellm.exceptions import ContentPolicyViolationError, RateLimitError

from vetinari.experts import Expert
from vetinari.llm import (
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

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        await cache.set("prompt1", value="response1")
        assert await cache.get("prompt1") == "response1"

    @pytest.mark.asyncio
    async def test_miss(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        assert await cache.get("unknown") is None

    @pytest.mark.asyncio
    async def test_different_model_keys(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        await cache.set("prompt", model="gpt-4o", value="gpt-response", temperature=0.0)
        await cache.set("prompt", model="groq/llama3", value="groq-response", temperature=0.0)
        assert await cache.get("prompt", model="gpt-4o", temperature=0.0) == "gpt-response"
        assert await cache.get("prompt", model="groq/llama3", temperature=0.0) == "groq-response"

    @pytest.mark.asyncio
    async def test_different_temperature_keys(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=10)
        await cache.set("prompt", model="gpt-4o", value="cold", temperature=0.0)
        await cache.set("prompt", model="gpt-4o", value="hot", temperature=1.0)
        assert await cache.get("prompt", model="gpt-4o", temperature=0.0) == "cold"
        assert await cache.get("prompt", model="gpt-4o", temperature=1.0) == "hot"

    @pytest.mark.asyncio
    async def test_max_entries_eviction(self) -> None:
        cache = SimpleCache(ttl_seconds=60, max_entries=3)
        await cache.set("p1", value="r1")
        await cache.set("p2", value="r2")
        await cache.set("p3", value="r3")
        await cache.set("p4", value="r4")
        # Oldest entry (p1) should be evicted
        assert await cache.get("p1") is None
        assert await cache.get("p4") == "r4"

    @pytest.mark.asyncio
    async def test_expired(self) -> None:
        cache = SimpleCache(ttl_seconds=0, max_entries=10)
        await cache.set("p1", value="r1")
        assert await cache.get("p1") is None


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
        assert resp.error_type is None  # can be set by router on real errors


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
        # Tried all 3 default models (generic Exception is not fatal)
        assert call_count[0] == 3
        assert response.fallback_used is True  # Phase 1: we did switch models
        assert response.error_type == "Exception"

        # Phase 0: Verify LiteLLM resilience parameters are passed
        first_call = mock_ac.call_args_list[0].kwargs
        assert "max_retries" in first_call
        assert "timeout" in first_call

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
        assert response.error_type == "Exception"

    @pytest.mark.asyncio
    async def test_fatal_error_fails_fast_no_fallback(self, expert: Expert) -> None:
        """Fatal errors must short-circuit (no fallback to other models) - Phase 1."""
        router = LLMRouter()
        call_count = [0]

        async def mock_fatal(**kwargs):
            call_count[0] += 1
            # Realistic constructor for litellm 1.x
            raise ContentPolicyViolationError(
                "Content policy violation",
                llm_provider="openai",
                model="gpt-4o-mini",
            )

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac,
            patch("litellm.completion_cost", return_value=0.0),
        ):
            mock_ac.side_effect = mock_fatal
            response = await router.consult(expert, "Test query")

        assert response.success is False
        assert response.error_type == "ContentPolicyViolationError"
        assert response.fallback_used is False  # critical: no model switch
        assert call_count[0] == 1  # did NOT try the other 2 models

    @pytest.mark.asyncio
    async def test_retriable_error_triggers_fallback_and_success(self, expert: Expert) -> None:
        """Rate limit on primary -> fallback succeeds with fallback_used=True."""
        router = LLMRouter()
        call_count = [0]

        async def mock_rate_then_ok(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RateLimitError(
                    "Rate limit",
                    llm_provider="anthropic",
                    model="claude-3-5-sonnet-20241022",
                )
            # second model succeeds
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "Fallback response"
            mock_resp.usage = MagicMock()
            mock_resp.usage.prompt_tokens = 5
            mock_resp.usage.completion_tokens = 3
            return mock_resp

        with (
            patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac,
            patch("litellm.completion_cost", return_value=0.0),
        ):
            mock_ac.side_effect = mock_rate_then_ok
            response = await router.consult(expert, "Test")

        assert response.success is True
        assert response.content == "Fallback response"
        assert response.fallback_used is True
        assert response.error_type is None  # success path
        assert call_count[0] == 2  # primary + 1 fallback

    @pytest.mark.asyncio
    async def test_fallback_used_true_on_success_from_secondary(self, expert: Expert) -> None:
        """Primary retriable fail -> secondary success: fallback_used + correct model."""
        router = LLMRouter()

        async def side(**kwargs):
            # Fail only first model, succeed on others
            model = kwargs.get("model", "")
            if "claude" in model or model == expert.recommended_model:
                raise RateLimitError("429", llm_provider="anthropic", model=model)
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = f"ok-from-{model}"
            mock_resp.usage = MagicMock()
            return mock_resp

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac, \
             patch("litellm.completion_cost", return_value=0.0):
            mock_ac.side_effect = side
            resp = await router.consult(expert, "Q")

        assert resp.success is True
        assert resp.fallback_used is True
        assert resp.model_used != expert.recommended_model  # used a fallback model

    @pytest.mark.asyncio
    async def test_resilience_settings_are_passed_to_litellm(self, expert: Expert) -> None:
        """max_retries and timeout from settings are forwarded to every litellm call (Phase 0+1)."""
        router = LLMRouter()

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_ac:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            mock_resp.usage = MagicMock()
            mock_ac.return_value = mock_resp
            with patch("litellm.completion_cost", return_value=0.0):
                await router.consult(expert, "Q")

        called = mock_ac.call_args_list[0].kwargs
        assert "max_retries" in called
        assert "timeout" in called
        # Concrete values tested via config + the Phase-0 fallback test; here we verify wiring.


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

    @pytest.mark.asyncio
    async def test_consult_multiple_respects_semaphore(self, experts: list[Expert]) -> None:
        """With max_concurrent=1, only one LLM call runs at a time."""
        router = LLMRouter(max_concurrent=1)
        concurrent = [0]
        max_seen = [0]

        async def mock_with_delay(**kwargs):
            concurrent[0] += 1
            max_seen[0] = max(max_seen[0], concurrent[0])
            await asyncio.sleep(0.05)
            concurrent[0] -= 1
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.usage = MagicMock()
            return mock_response

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_with_delay
            with patch("litellm.completion_cost", return_value=0.0):
                await router.consult_multiple(experts, "Test query")

        assert max_seen[0] == 1

    @pytest.mark.asyncio
    async def test_semaphore_default_allows_parallel(self, experts: list[Expert]) -> None:
        """With max_concurrent=4, three experts can run in parallel."""
        router = LLMRouter(max_concurrent=4)
        concurrent = [0]
        max_seen = [0]

        async def mock_with_delay(**kwargs):
            concurrent[0] += 1
            max_seen[0] = max(max_seen[0], concurrent[0])
            await asyncio.sleep(0.05)
            concurrent[0] -= 1
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Response"
            mock_response.usage = MagicMock()
            return mock_response

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_with_delay
            with patch("litellm.completion_cost", return_value=0.0):
                await router.consult_multiple(experts, "Test query")

        assert max_seen[0] == 3


class TestLLMRouterCacheConcurrency:
    """Tests for cache under concurrent access."""

    @pytest.fixture
    def expert(self) -> Expert:
        return Expert(
            id="cache-expert",
            name="Cache Expert",
            description="D",
            prompt="You are a test expert.",
            recommended_model="gpt-4o-mini",
        )

    @pytest.mark.asyncio
    async def test_cache_concurrent_access(self, expert: Expert) -> None:
        """Concurrent consults with same prompt: cache serves follow-up without LLM."""
        router = LLMRouter(enable_cache=True, max_concurrent=4)
        call_count = [0]

        async def mock_llm(**kwargs):
            call_count[0] += 1
            await asyncio.sleep(0.02)
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Cached response"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            return mock_response

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_llm
            with patch("litellm.completion_cost", return_value=0.0):
                responses = await asyncio.gather(
                    router.consult(expert, "Same query?"),
                    router.consult(expert, "Same query?"),
                    router.consult(expert, "Same query?"),
                )

        assert all(r.content == "Cached response" for r in responses)
        initial_calls = call_count[0]
        assert initial_calls >= 1

        await router.consult(expert, "Same query?")
        assert call_count[0] == initial_calls
