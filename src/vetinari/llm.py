"""Simplified LiteLLM wrapper — primary + fallback model, optional cache."""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from dataclasses import dataclass, field

import structlog

from vetinari.config import DEFAULT_FALLBACK_MODELS, settings
from vetinari.experts import Expert

logger = structlog.get_logger(__name__)

# ── Resilience Error Classification (Phase 1) ────────────────────────────────
# Only these are treated as fatal for *all* models (prompt-intrinsic).
# All other litellm errors (rate limits, auth per provider, timeouts, 5xx, conn)
# still trigger fallback after backoff. Mixed providers make this the right default.
try:
    from litellm.exceptions import ContentPolicyViolationError, ContextWindowExceededError

    FATAL_ERRORS: tuple[type[BaseException], ...] = (
        ContentPolicyViolationError,
        ContextWindowExceededError,
    )
except Exception:
    FATAL_ERRORS = ()


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
    error_type: str | None = None
    error_category: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def classify_error(error: BaseException | None, error_type: str | None = None) -> str | None:
    """Map exceptions to stable MCP-friendly error categories."""
    if error is not None:
        name = type(error).__name__
    elif error_type:
        name = error_type
    else:
        return None

    categories: dict[str, str] = {
        "RateLimitError": "rate_limit",
        "Timeout": "timeout",
        "AuthenticationError": "auth",
        "InvalidAPIKeyError": "auth",
        "ContentPolicyViolationError": "content_policy",
        "ContextWindowExceededError": "context_window",
        "ServiceUnavailableError": "service_unavailable",
        "APIConnectionError": "connection",
        "InternalServerError": "server_error",
    }
    return categories.get(name, "unknown")


# ── Simple In-Memory Cache (opt-in) ──────────────────────────────────────────


class SimpleCache:
    """Minimal TTL cache with asyncio lock for concurrent access."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 500) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._data: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    def _key(self, prompt: str, model: str, temperature: float, max_tokens: int) -> str:
        raw = f"{prompt}|{model}|{temperature}|{max_tokens}"
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get(
        self,
        prompt: str,
        model: str = "",
        temperature: float = 0.0,
        max_tokens: int = 0,
    ) -> str | None:
        async with self._lock:
            key = self._key(prompt, model, temperature, max_tokens)
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                del self._data[key]
                return None
            return value

    async def set(
        self,
        prompt: str,
        model: str = "",
        value: str = "",
        temperature: float = 0.0,
        max_tokens: int = 0,
    ) -> None:
        async with self._lock:
            key = self._key(prompt, model, temperature, max_tokens)
            if len(self._data) >= self._max:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (time.monotonic(), value)


# ── Resilience Helpers ───────────────────────────────────────────────────────


async def _sleep_with_backoff(attempt: int, base_delay: float) -> float:
    """Exp backoff + jitter (capped). Returns actual delay slept (for logging)."""
    delay = min(base_delay * (2 ** attempt), 8.0)
    jitter = random.uniform(0, delay * 0.25)
    total = delay + jitter
    await asyncio.sleep(total)
    return total


# ── LLM Router ───────────────────────────────────────────────────────────────


DEFAULT_MODELS = DEFAULT_FALLBACK_MODELS


def _select_primary_model(expert: Expert, model: str | None) -> str:
    """Resolve the first model to try: explicit > expert > fallback chain > default."""
    if model:
        return model
    if expert.recommended_model:
        return expert.recommended_model
    if settings.fallback_models:
        return settings.fallback_models[0]
    return settings.default_model


class LLMRouter:
    """Simple LLM router: primary model → fallback, optional cache."""

    def __init__(
        self,
        models: list[str] | None = None,
        enable_cache: bool = False,
        max_concurrent: int | None = None,
    ) -> None:
        self.models = list(models) if models is not None else list(settings.fallback_models)
        self._semaphore = asyncio.Semaphore(max_concurrent or settings.llm_max_concurrent)
        self.cache = SimpleCache(
            ttl_seconds=settings.cache_ttl_seconds,
            max_entries=settings.cache_max_entries,
        ) if enable_cache else None
        self._in_flight: dict[str, asyncio.Task[ExpertAdviceResponse]] = {}
        self._in_flight_lock = asyncio.Lock()

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
        selected_model = _select_primary_model(expert, model)
        temp = temperature if temperature is not None else settings.default_temperature
        max_tok = max_tokens or settings.max_tokens

        system_prompt = expert.prompt
        cache_key = f"<system>{system_prompt}</system>\n<user>{user_query}</user>"

        if self.cache:
            cached = await self.cache.get(cache_key, selected_model, temp, max_tok)
            if cached:
                logger.info("cache_hit", expert_id=expert.id, model=selected_model)
                return ExpertAdviceResponse(
                    expert_id=expert.id,
                    expert_name=expert.name,
                    model_used=selected_model,
                    content=cached,
                    retrieval_time_ms=(time.monotonic() - start_time) * 1000,
                )

            flight_key = hashlib.sha256(
                f"{cache_key}|{selected_model}|{temp}|{max_tok}".encode(),
            ).hexdigest()
            async with self._in_flight_lock:
                inflight = self._in_flight.get(flight_key)
                if inflight is not None:
                    return await asyncio.shield(inflight)
                task = asyncio.create_task(
                    self._consult_with_llm(
                        expert, user_query, selected_model, temp, max_tok, start_time, cache_key,
                    ),
                )
                self._in_flight[flight_key] = task

            try:
                return await task
            finally:
                async with self._in_flight_lock:
                    if self._in_flight.get(flight_key) is task:
                        del self._in_flight[flight_key]

        return await self._consult_with_llm(
            expert, user_query, selected_model, temp, max_tok, start_time, cache_key,
        )

    async def _consult_with_llm(
        self,
        expert: Expert,
        user_query: str,
        selected_model: str,
        temp: float,
        max_tok: int,
        start_time: float,
        cache_key: str,
    ) -> ExpertAdviceResponse:
        """Run LLM fallback loop; optionally populate cache on success."""
        system_prompt = expert.prompt
        models_to_try = [selected_model] + [m for m in self.models if m != selected_model]
        last_error: str | None = None
        last_error_type: str | None = None
        last_error_category: str | None = None
        fallback_used = False

        max_retries = settings.llm_max_retries
        base_delay = settings.llm_retry_base_delay_seconds
        timeout = settings.llm_timeout_seconds

        for attempt, model_name in enumerate(models_to_try):
            if attempt > 0:
                fallback_used = True
                logger.info(
                    "fallback_attempt",
                    from_model=selected_model,
                    to_model=model_name,
                    attempt=attempt,
                )

            try:
                async with self._semaphore:
                    result = await self._call_llm(
                        model_name,
                        system_prompt,
                        user_query,
                        temp,
                        max_tok,
                        timeout=timeout,
                        max_retries=max_retries,
                    )

                # Cache if enabled
                if self.cache:
                    await self.cache.set(cache_key, model_name, result["content"], temp, max_tok)

                usage = UsageInfo(
                    prompt_tokens=result.get("prompt_tokens", 0),
                    completion_tokens=result.get("completion_tokens", 0),
                    cost_usd=result.get("cost", 0.0),
                )

                elapsed_ms = (time.monotonic() - start_time) * 1000
                logger.info(
                    "consult_success",
                    expert_id=expert.id,
                    model=model_name,
                    elapsed_ms=round(elapsed_ms, 1),
                    max_retries_configured=max_retries,
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
                last_error_type = type(e).__name__
                last_error_category = classify_error(e)
                logger.error(
                    "llm_call_failed",
                    model=model_name,
                    error=last_error,
                    error_type=last_error_type,
                    attempt=attempt,
                    max_retries_configured=max_retries,
                )

                is_fatal = bool(FATAL_ERRORS) and isinstance(e, FATAL_ERRORS)
                if is_fatal:
                    # Short-circuit: no point trying other models for prompt-intrinsic fatal errors
                    # (policy violation, context window). Prevents unnecessary cost/latency.
                    break

                if attempt < len(models_to_try) - 1:
                    # Log exact delay from the (now observable) helper
                    actual_delay = await _sleep_with_backoff(attempt, base_delay)
                    next_idx = attempt + 1
                    next_m = models_to_try[next_idx] if next_idx < len(models_to_try) else None
                    logger.info(
                        "model_fallback_backoff",
                        from_model=model_name,
                        to_model=next_m,
                        delay_seconds=round(actual_delay, 3),
                        attempt=attempt,
                    )

        # All models failed (or short-circuited on fatal)
        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.error("all_models_failed", expert_id=expert.id)
        return ExpertAdviceResponse(
            expert_id=expert.id,
            expert_name=expert.name,
            model_used=selected_model,
            content="",
            retrieval_time_ms=elapsed_ms,
            error=last_error or "All models failed",
            error_type=last_error_type,
            error_category=last_error_category or classify_error(None, last_error_type),
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
        *,
        timeout: float | None = None,
        max_retries: int = 0,
    ) -> dict:
        """Call an LLM via litellm. Returns dict with content, tokens, cost.

        LiteLLM's max_retries handles transient errors (rate limits, timeouts, 5xx)
        internally with its own backoff before we fall back to another model.
        """
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
            timeout=timeout,
            max_retries=max_retries,
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
