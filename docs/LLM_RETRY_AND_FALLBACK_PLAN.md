# Plan: Robust Retry + Fallback Logic for LLM Calls

**Status**: Phase 0 implemented (2026-05) — see `feat/llm-resilience` branch  
**Owner**: (to be assigned)  
**Related Issue**: LLM calls can fail due to Rate Limits (429), Timeouts, transient API errors (5xx, connection resets), model unavailability.  
**Goal**: Make `consult_expert` and `consult_multiple_experts` resilient without sacrificing the "lean" character of Vetinari.

---

## 1. Current State (as of `refactor/rename-to-vetinari`)

### What exists today (`src/vetinari/llm.py`)

- **Cross-model fallback** in `LLMRouter.consult()` (lines 151–209):
  - Tries `selected_model` first, then the other models from `DEFAULT_MODELS`.
  - On *any* `Exception`, logs, sleeps a **fixed 1 second**, tries the next model.
  - After all models exhausted → returns `ExpertAdviceResponse` with `error=...` and `success=False`.
- **No per-model retries** — each model is attempted exactly once.
- `_call_llm()` (lines 229–267) performs a raw `litellm.acompletion(...)` with **zero** `max_retries`, `timeout`, or backoff parameters.
- Error handling is a broad `except Exception`.
- `consult_multiple()` uses plain `asyncio.gather` (no concurrency limiting).
- **Cache** is only populated on success.
- Logging exists for `llm_call_failed`, `fallback_attempt`, `all_models_failed`.

### What is missing

| Weakness | Impact | Location |
|----------|--------|----------|
| No retries on transient errors for the *same* model | Rate limit on Claude → immediately wastes a fallback to GPT-4o-mini | `consult()` + `_call_llm()` |
| Fixed `sleep(1.0)` between models | Thundering herd risk, poor UX on repeated 429s | line 196 |
| No `timeout` passed to LiteLLM | Hanging requests possible | `_call_llm()` |
| No error classification (retriable vs fatal) | `AuthenticationError` or bad prompt triggers unnecessary fallbacks | `except Exception` |
| No configuration for retry behavior | Hard to tune per deployment / provider | `config.py` (none) |
| LiteLLM's built-in retry support unused | We reinvent (poorly) what the library already does | — |
| Parallel calls can amplify rate limits | `consult_multiple_experts` with 4 experts can hit limits hard | `consult_multiple()` |
| Tests only cover "fail all models" scenario | No coverage of successful retry-after-N-attempts | `tests/test_llm.py:163` |

**Result**: The system is brittle in real-world usage (especially with Anthropic rate limits or DeepSeek instability).

---

## 2. Design Principles (must respect "Lean" philosophy)

- **Minimal surface area** — prefer configuring LiteLLM over adding 200 lines of custom retry code.
- **Observable** — every retry/fallback must produce clear structured logs.
- **Configurable via `.env`** — no code changes needed for tuning.
- **Testable in isolation** — mock only the `litellm.acompletion` boundary.
- **Backwards compatible** — existing error responses and `fallback_used` semantics stay stable.
- **No heavy new frameworks** — avoid full `litellm.Router` rewrite unless justified.

---

## 3. Recommended Approach (Hybrid – Lean + Effective)

### Phase 0 – Quick Wins (1–2 hours, very low risk)

1. Pass LiteLLM-native retry & timeout parameters in `_call_llm()`:
   ```python
   response = await litellm.acompletion(
       ...,
       timeout=settings.llm_timeout_seconds,
       max_retries=settings.llm_max_retries,   # LiteLLM handles 429, 5xx, timeouts internally
   )
   ```
2. Add three new settings in `config.py`:
   - `llm_max_retries: int = 2`
   - `llm_retry_base_delay_seconds: float = 0.5` (used only for *model* fallback delay)
   - `llm_timeout_seconds: float | None = 90.0`
3. Make the sleep between model attempts **exponential + jitter** (tiny pure-Python helper, ~15 lines).
4. Log `retry_attempt`, `delay_seconds`, and the concrete exception type.
5. Update the two existing fallback tests to also assert that `max_retries` is passed.

This alone gives **dramatically better behavior** because LiteLLM already knows which errors are retriable.

### Phase 1 – Proper Error Classification & Per-Model Retries (half day)

- Import retriable exceptions from `litellm.exceptions` (with safe fallback):
  ```python
  from litellm.exceptions import (
      RateLimitError, APIError, Timeout, ServiceUnavailableError,
      APIConnectionError, InternalServerError
  )
  RETRIABLE = (RateLimitError, Timeout, ServiceUnavailableError, ...)
  ```
- In the fallback loop, only count a model as "failed" after its internal LiteLLM retries + one outer classification check.
- Optional small wrapper `_call_with_retries()` that can do additional application-level retries on top of LiteLLM's (for cases where we want custom jitter or provider-specific logic).
- Expose `fallback_used` more accurately (only true when we actually switched models after exhausting retries on the primary).

### Phase 2 – Parallel Call Hardening (optional, nice-to-have)

- Add an `asyncio.Semaphore` (limit concurrent LLM calls, e.g. 4–6) when `consult_multiple` is used.
- Or document that users should not call all 4 experts with very high frequency.
- Consider per-provider rate-limit awareness (advanced).

### Phase 3 – Future (only if pain reported)

- Adopt `litellm.Router` for cooldowns, fallbacks with latency tracking, content-based routing.
- Add circuit breaker per model.
- Structured error taxonomy returned to clients (`error_type: "rate_limit" | "timeout" | "auth" | ...`).

---

## 4. Concrete Changes

### 4.1 `src/vetinari/config.py`

Add under `# LLM defaults`:

```python
# LLM resilience (Phase 0+)
llm_max_retries: int = 2
llm_retry_base_delay_seconds: float = 0.5
llm_timeout_seconds: float | None = 90.0
```

### 4.2 `src/vetinari/llm.py`

- Add helper (new, small):
  ```python
  async def _sleep_with_backoff(attempt: int, base_delay: float) -> None:
      delay = min(base_delay * (2 ** attempt), 8.0)
      jitter = random.uniform(0, delay * 0.1)  # full jitter style
      await asyncio.sleep(delay + jitter)
  ```
  (Need `import random`)

- Modify `_call_llm(...)` signature to accept/forward retry & timeout settings.
- Change the call site to pass the new settings.
- Improve the `for attempt, model_name in enumerate(models_to_try)` loop:
  - After a failed model (post LiteLLM retries), call the backoff sleeper before trying the next model.
- Update docstrings and the `ExpertAdviceResponse` if we want to expose `retry_count` (optional, for observability).

- Keep `SimpleCache` behavior: only cache successful final answers.

### 4.3 `src/vetinari/server.py`

- No functional change required.
- Optionally surface `retry_count` or `attempts` in the JSON response (nice for Cursor/Claude users debugging).

### 4.4 Tests (`tests/test_llm.py`)

- Add `test_consult_retries_on_transient_error_then_succeeds`
- Add `test_consult_respects_max_retries_setting`
- Add `test_timeout_is_passed_to_litellm`
- Parameterize existing fallback tests with different `max_retries`.

Use `AsyncMock` side_effect lists that fail N times then succeed.

### 4.5 Documentation & DX

- Update `README.md` "Features" section:
  > **Resilient calls** — automatic retries (via LiteLLM) + cross-model fallback with exponential backoff + jitter.
- Add new `.env` example lines.
- Update `CLAUDE.md` key files / config section.
- Consider a small "Reliability" subsection.

### 4.6 Dependency

**Decision**: **No new runtime dependency for Phase 0/1**.

- We leverage `litellm>=1.40` built-in `max_retries` + `timeout`.
- The tiny `_sleep_with_backoff` is pure stdlib + `random`.
- Only if we later need sophisticated retry policies (custom conditions, circuit breakers) do we consider `tenacity>=8.2` (very small wheel).

---

## 5. Rollout Plan

| Phase | Scope | Tests | Docs | Risk | PR Size |
|-------|-------|-------|------|------|---------|
| 0     | LiteLLM params + tiny backoff sleeper + 3 config knobs | Extend 2 existing tests | README + .env.example | Very Low | Small |
| 1     | Error classification + better `fallback_used` semantics + logs | 3–4 new focused tests | CLAUDE.md + plan doc | Low | Medium |
| 2     | Semaphore for parallel calls (if needed) | — | — | Medium | Small |

**Success Criteria**:
- A single transient 429 on primary model no longer immediately switches models.
- `max_retries=0` still works (for strict latency budgets).
- All 39+ existing tests continue to pass.
- New behavior is visible in structured logs (`retry_attempt`, `delay_seconds`).

---

## 6. Open Questions / Trade-offs

1. Should `fallback_used=True` only be set after exhausting retries on the primary, or on the first switch?
2. Do we want to return `attempts_made` or `retries_performed` in the tool response? (increases response size slightly)
3. Should cache be keyed including the final successful model, or only the requested one? (current behavior is fine)
4. How aggressive should the semaphore be (if Phase 2)? Default 5 concurrent LLM calls?
5. Should we make the list of "retriable exception types" configurable? (probably overkill)

---

## 7. References

- LiteLLM docs: [Completion Retries & Timeouts](https://docs.litellm.ai/docs/completion/retry)
- Current implementation: `src/vetinari/llm.py:151` (fallback loop), `229` (`_call_llm`)
- Existing tests: `tests/test_llm.py:163` (`test_consult_fallback_on_error`)

---

**Next Steps (for implementer)**

1. Review & approve this plan (or suggest changes).
2. Implement Phase 0 on a feature branch `feat/llm-resilience`.
3. Run full test suite + manual rate-limit simulation (e.g. using `pytest-httpx` or monkey-patching).
4. Update user-facing docs.
5. Merge + release note.

This plan keeps Vetinari lean while making it production-grade for the exact failure modes mentioned (Rate Limits, Timeouts, API errors).

---

*Generated after code review of `llm.py`, `config.py`, `server.py` and relevant tests on the current `vetinari` codebase.*