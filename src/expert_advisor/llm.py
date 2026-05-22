"""Simplified LiteLLM wrapper — primary + fallback model, optional cache."""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field

import structlog

from expert_advisor.config import settings
from expert_advisor.experts import Expert

logger = structlog.get_logger(__name__)


# ── Data Structures ──────────────────────────────────────────────────────────


@dataclass
class UsageInfo:
    """Minimal token/cost info for a single call."""

    model: str = "unknown"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class ExpertAdviceResponse:
    """Structured response from an expert consultation."""

    expert_id: str
    expert_name: str
    model_used: str
    content: str
    usage: UsageInfo = field(default_factory=UsageInfo)
    fallback_used: bool = False
    retrieval_time_ms: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


# ── Simple In-Memory Cache (opt-in) ──────────────────────────────────────────


class SimpleCache:
    """Minimal TTL cache — no locking needed for single-user scenario."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 500) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._data: dict[str, tuple[float, str]] = {}

    def _key(self, prompt: str, model: str, temperature: float, max_tokens: int) -> str:
        raw = f"{prompt}|{model}|{temperature}|{max_tokens}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self,
        prompt: str,
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 0,
    ) -> str | None:
        key = self._key(prompt, model, temperature, max_tokens)
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > self._ttl:
            del self._data[key]
            return None
        return value

    def set(
        self,
        prompt: str,
        model: str = "",
        value: str = "",
        temperature: float = 0.0,
        max_tokens: int = 0,
    ) -> None:
        key = self._key(prompt, model, temperature, max_tokens)
        if len(self._data) >= self._max:
            # Remove oldest entry
            oldest = min(self._data, key=lambda k: self._data[k][0])
            del self._data[oldest]
        self._data[key] = (time.monotonic(), value)


# ── Simple Cost Log ──────────────────────────────────────────────────────────


@dataclass
class CostLog:
    """Minimal cumulative cost/token log."""

    total_tokens: int = 0
    total_cost: float = 0.0
    total_calls: int = 0
    successful_calls: int = 0

    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        success: bool = True,
    ) -> UsageInfo:
        self.total_calls += 1
        if success:
            self.successful_calls += 1
            self.total_tokens += prompt_tokens + completion_tokens
            self.total_cost += cost
        return UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
        )

    @property
    def summary(self) -> str:
        return (
            f"calls={self.total_calls} success={self.successful_calls} "
            f"tokens={self.total_tokens} cost=${self.total_cost:.6f}"
        )


# ── LLM Router ───────────────────────────────────────────────────────────────


DEFAULT_MODELS = [
    "anthropic/claude-3-5-sonnet-20241022",
    "gpt-4o-mini",
    "deepseek/deepseek-chat",
]


class LLMRouter:
    """Simple LLM router: primary model → fallback, optional cache, cost log."""

    def __init__(
        self,
        models: list[str] | None = None,
        enable_cache: bool = False,
    ) -> None:
        self.models = list(models) if models else list(DEFAULT_MODELS)
        self.cache = SimpleCache(
            ttl_seconds=settings.cache_ttl_seconds,
            max_entries=settings.cache_max_entries,
        ) if enable_cache else None
        self.cost_log = CostLog()

    async def consult(
        self,
        expert: Expert,
        user_query: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ExpertAdviceResponse:
        """Consult a single expert with fallback."""
        start_time = time.monotonic()
        selected_model = model or expert.recommended_model or settings.default_model
        temp = temperature if temperature is not None else settings.default_temperature
        max_tok = max_tokens or settings.max_tokens

        system_prompt = expert.prompt
        cache_key = f"<system>{system_prompt}</system>\n<user>{user_query}</user>"

        # Check cache if enabled
        if self.cache:
            cached = self.cache.get(cache_key, selected_model, temp, max_tok)
            if cached:
                logger.info("cache_hit", expert_id=expert.id, model=selected_model)
                return ExpertAdviceResponse(
                    expert_id=expert.id,
                    expert_name=expert.name,
                    model_used=selected_model,
                    content=cached,
                    retrieval_time_ms=(time.monotonic() - start_time) * 1000,
                )

        # Try primary then fallback
        models_to_try = [selected_model] + [m for m in self.models if m != selected_model]
        last_error: str | None = None
        fallback_used = False

        for attempt, model_name in enumerate(models_to_try):
            if attempt > 0:
                fallback_used = True
                logger.info("fallback_attempt", from_model=selected_model, to_model=model_name)

            try:
                result = await self._call_llm(model_name, system_prompt, user_query, temp, max_tok)

                # Cache if enabled
                if self.cache:
                    self.cache.set(cache_key, model_name, result["content"], temp, max_tok)

                # Log cost
                usage = self.cost_log.record(
                    prompt_tokens=result.get("prompt_tokens", 0),
                    completion_tokens=result.get("completion_tokens", 0),
                    cost=result.get("cost", 0.0),
                )

                elapsed_ms = (time.monotonic() - start_time) * 1000
                logger.info(
                    "consult_success",
                    expert_id=expert.id,
                    model=model_name,
                    elapsed_ms=round(elapsed_ms, 1),
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
                last_error = str(e)
                logger.error("llm_call_failed", model=model_name, error=last_error)
                if attempt < len(models_to_try) - 1:
                    await asyncio.sleep(1.0)

        # All models failed
        elapsed_ms = (time.monotonic() - start_time) * 1000
        self.cost_log.record(success=False)
        logger.error("all_models_failed", expert_id=expert.id)
        return ExpertAdviceResponse(
            expert_id=expert.id,
            expert_name=expert.name,
            model_used=selected_model,
            content="",
            retrieval_time_ms=elapsed_ms,
            error=last_error or "All models failed",
            fallback_used=fallback_used,
        )

    async def consult_multiple(
        self,
        experts: list[Expert],
        user_query: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> list[ExpertAdviceResponse]:
        """Consult multiple experts in parallel."""
        tasks = [
            self.consult(
                expert, user_query,
                model=model, temperature=temperature, max_tokens=max_tokens,
            )
            for expert in experts
        ]
        return await asyncio.gather(*tasks)

    async def _call_llm(
        self,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Call an LLM via litellm. Returns dict with content, tokens, cost."""
        import litellm

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
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

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
