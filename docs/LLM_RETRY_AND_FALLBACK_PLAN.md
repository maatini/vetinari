# LLM Resilience — Implementation Status

**Status**: Phases 0–2 implemented (2026-05)  
**Code**: `src/vetinari/llm.py`, `src/vetinari/config.py`

## Implemented

| Feature | Location |
|---------|----------|
| LiteLLM `max_retries` + `timeout` | `_call_llm()` |
| Cross-model fallback with exponential backoff + jitter | `_consult_with_llm()` |
| Fatal-error short-circuit (content policy, context window) | `FATAL_ERRORS` in `llm.py` |
| `error_type` + `error_category` in responses | `ExpertAdviceResponse`, MCP JSON |
| Concurrency limit for parallel consults | `asyncio.Semaphore` in `LLMRouter` |
| Key-aware model prioritization | `prioritize_models_by_keys()` in `config.py` |
| API keys from `.env` → `os.environ` for LiteLLM | `sync_api_keys_to_env()` |
| `partial_success` aggregation | `consult_multiple_experts` in `server.py` |

## Config (`.env`)

```bash
LLM_MAX_RETRIES=2
LLM_RETRY_BASE_DELAY_SECONDS=0.5
LLM_TIMEOUT_SECONDS=90
LLM_MAX_CONCURRENT=4
FALLBACK_MODELS=anthropic/claude-sonnet-4-6,gpt-4o-mini,deepseek/deepseek-chat
```

## Deferred (no reported pain)

- `litellm.Router` with cooldowns / circuit breakers
- Per-provider rate-limit awareness beyond semaphore
- `retry_count` in MCP tool responses

## Tests

Resilience behavior covered in `tests/test_llm.py` (fallback, fatal fast-fail, semaphore, cache concurrency).  
Config wiring in `tests/test_config.py`. Server response shape in `tests/test_server.py`.
