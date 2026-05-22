"""LLM Router — wraps LiteLLM with fallback, caching, rate limiting, and retries."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import structlog

from expert_advisor.config import settings
from expert_advisor.experts.prompts import Expert
from expert_advisor.utils.cost_tracker import CostTracker, UsageInfo

logger = structlog.get_logger(__name__)


# ── Data Structures ─────────────────────────────────────────────────────────


@dataclass
class ExpertAdviceResponse:
    """Structured response from an expert consultation."""

    expert_id: str
    expert_name: str
    model_used: str
    content: str
    usage: UsageInfo
    fallback_used: bool = False
    retrieval_time_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class ModelConfig:
    """Configuration for a single LLM model/provider."""

    model: str
    api_key_var: str
    priority: int = 0  # Lower = higher priority
    rpm_limit: int = 100  # Requests per minute


# ── Default Model Configurations ─────────────────────────────────────────────

DEFAULT_MODELS = [
    # Priority 0: Best/cheapest primary models
    ModelConfig(model="gpt-4o-mini", api_key_var="OPENAI_API_KEY", priority=0),
    # Priority 1: Fallback models
    ModelConfig(
        model="anthropic/claude-3-5-sonnet-20240620",
        api_key_var="ANTHROPIC_API_KEY",
        priority=1,
    ),
    ModelConfig(model="gemini/gemini-2.0-flash", api_key_var="GEMINI_API_KEY", priority=1),
    ModelConfig(model="deepseek/deepseek-chat", api_key_var="DEEPSEEK_API_KEY", priority=1),
    ModelConfig(model="groq/llama3-70b-8192", api_key_var="GROQ_API_KEY", priority=2),
    # Priority 3: Cheapest fallback
    ModelConfig(model="gpt-3.5-turbo", api_key_var="OPENAI_API_KEY", priority=3),
]


# ── In-Memory Cache ──────────────────────────────────────────────────────────


class TTLCache:
    """Simple TTL-based in-memory cache with LRU eviction."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._data: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def _key(self, prompt: str, model: str = "") -> str:
        """Generate a cache key from prompt hash."""
        return hashlib.sha256(prompt.encode()).hexdigest()

    def get(self, prompt: str, model: str = "") -> str | None:
        key = self._key(prompt)
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        # Move to end for LRU
        self._data.move_to_end(key)
        return value

    def set(self, prompt: str, model: str = "", value: str = "") -> None:
        key = self._key(prompt)
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self._max:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


# ── Rate Limiter ─────────────────────────────────────────────────────────────


class RateLimiter:
    """Sliding window rate limiter per model."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 30) -> None:
        self._window = window_seconds
        self._max = max_requests
        self._timestamps: dict[str, list[float]] = {}

    def _cleanup(self, model: str) -> None:
        now = time.monotonic()
        ts_list = self._timestamps.get(model, [])
        self._timestamps[model] = [t for t in ts_list if now - t < self._window]

    def check(self, model: str) -> bool:
        """Return True if request is allowed."""
        self._cleanup(model)
        return len(self._timestamps.get(model, [])) < self._max

    def record(self, model: str) -> None:
        self._timestamps.setdefault(model, []).append(time.monotonic())


# ── LLM Router ───────────────────────────────────────────────────────────────


class LLMRouter:
    """Routes LLM requests through LiteLLM with fallback, caching, and rate limiting."""

    def __init__(
        self,
        models: list[ModelConfig] | None = None,
        cache_ttl: int | None = None,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self.models = sorted(models or DEFAULT_MODELS, key=lambda m: m.priority)
        self.cache = TTLCache(
            ttl_seconds=cache_ttl or settings.cache_ttl_seconds,
            max_entries=settings.cache_max_entries,
        )
        self.rate_limiter = RateLimiter(
            window_seconds=settings.rate_limit_window_seconds,
            max_requests=settings.rate_limit_max_requests,
        )
        self.cost_tracker = cost_tracker or CostTracker()

    async def consult(
        self,
        expert: Expert,
        user_query: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ExpertAdviceResponse:
        """Consult a single expert with automatic model selection and fallback."""
        start_time = time.monotonic()

        # Determine model
        selected_model = model or expert.recommended_model or settings.default_model
        temp = temperature or settings.default_temperature
        max_tok = max_tokens or settings.max_tokens

        # Build the full prompt
        system_prompt = expert.prompt
        user_message = user_query

        # Check cache
        cache_key = f"<system>{system_prompt}</system>\n<user>{user_message}</user>"
        cached = self.cache.get(cache_key, selected_model)
        if cached:
            logger.info("cache_hit", expert_id=expert.id, model=selected_model)
            return ExpertAdviceResponse(
                expert_id=expert.id,
                expert_name=expert.name,
                model_used=selected_model,
                content=cached,
                usage=UsageInfo(model=selected_model, cached=True),
                retrieval_time_ms=(time.monotonic() - start_time) * 1000,
            )

        # Try models in priority order (fallback)
        models_to_try = [selected_model] + [
            m.model for m in self.models if m.model != selected_model
        ]

        last_error: str | None = None
        fallback_used = False

        for attempt, model_name in enumerate(models_to_try):
            if attempt > 0:
                fallback_used = True
                logger.info(
                    "fallback_attempt",
                    from_model=selected_model,
                    to_model=model_name,
                    reason=last_error,
                )

            # Check rate limit
            if not self.rate_limiter.check(model_name):
                logger.warning("rate_limited", model=model_name)
                last_error = f"Rate limit exceeded for {model_name}"
                continue

            try:
                result = await self._call_llm(
                    model=model_name,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temp,
                    max_tokens=max_tok,
                )

                # Record rate limit usage
                self.rate_limiter.record(model_name)

                # Cache successful result
                self.cache.set(cache_key, model_name, result["content"])

                # Track cost
                usage = self.cost_tracker.record(
                    model=model_name,
                    prompt_tokens=result.get("prompt_tokens", 0),
                    completion_tokens=result.get("completion_tokens", 0),
                    cost=result.get("cost", 0.0),
                )

                elapsed_ms = (time.monotonic() - start_time) * 1000
                logger.info(
                    "consult_success",
                    expert_id=expert.id,
                    model=model_name,
                    fallback=fallback_used,
                    elapsed_ms=round(elapsed_ms, 1),
                    cost=round(usage.cost_usd, 6),
                )

                return ExpertAdviceResponse(
                    expert_id=expert.id,
                    expert_name=expert.name,
                    model_used=model_name,
                    content=result["content"],
                    usage=usage,
                    fallback_used=fallback_used,
                    retrieval_time_ms=elapsed_ms,
                )

            except Exception as e:
                logger.error(
                    "llm_call_failed",
                    model=model_name,
                    error=str(e),
                    attempt=attempt + 1,
                )
                last_error = str(e)
                # Retry with backoff
                if attempt < len(models_to_try) - 1:
                    delay = min(
                        settings.retry_base_delay_seconds * (2**attempt),
                        settings.retry_max_delay_seconds,
                    )
                    await asyncio.sleep(delay)

        # All models failed
        elapsed_ms = (time.monotonic() - start_time) * 1000
        self.cost_tracker.record(model=selected_model, success=False)
        logger.error("all_models_failed", expert_id=expert.id, last_error=last_error)
        return ExpertAdviceResponse(
            expert_id=expert.id,
            expert_name=expert.name,
            model_used=selected_model,
            content="",
            usage=UsageInfo(model=selected_model, success=False),
            retrieval_time_ms=elapsed_ms,
            error=last_error or "All models failed",
            fallback_used=fallback_used,
        )

    async def consult_multiple(
        self,
        experts: list[Expert],
        user_query: str,
        **kwargs: Any,
    ) -> list[ExpertAdviceResponse]:
        """Consult multiple experts in parallel."""
        tasks = [self.consult(expert, user_query, **kwargs) for expert in experts]
        return await asyncio.gather(*tasks)

    async def _call_llm(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Call an LLM via litellm. Returns dict with content, tokens, cost."""
        import litellm

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await litellm.acompletion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.choices[0].message.content or ""

        # Extract token usage
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

        # Calculate cost via litellm
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        return {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
        }

    def _find_api_key_var(self, model: str) -> str | None:
        """Find the API key environment variable for a model."""
        model_lower = model.lower()
        for mc in self.models:
            if mc.model.lower() == model_lower:
                return mc.api_key_var
        # Try litellm's provider mapping
        import litellm
        try:
            provider = litellm.get_llm_provider(model)
            if provider == "openai":
                return "OPENAI_API_KEY"
            elif provider == "anthropic":
                return "ANTHROPIC_API_KEY"
            elif "gemini" in provider:
                return "GEMINI_API_KEY"
            elif "deepseek" in provider:
                return "DEEPSEEK_API_KEY"
            elif "groq" in provider:
                return "GROQ_API_KEY"
        except Exception:
            pass
        return None


# Module-level singleton
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get or create the global LLM router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
