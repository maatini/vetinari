# Vetinari — pi context

## Project
MCP server: 4 expert advisors via LLMs. LiteLLM routing, FastMCP, parallel consultation.

## Quick commands
- `devbox run test` — run tests
- `devbox run test-cov` — tests with coverage
- `devbox run server` — start MCP server
- (demo script removed — use MCP tools or `devbox run server`)
- `uv run ruff check src/ tests/` — lint

## Key files
- `src/vetinari/server.py` — FastMCP server with 4 tools
- `src/vetinari/llm.py` — LiteLLM wrapper (fallback, optional cache)
- `src/vetinari/experts.py` — 4 experts + registry
- `src/vetinari/config.py` — pydantic-settings config
- `tests/` — 50+ tests (lean, consolidated into test_llm.py + focused server tests)

## Architecture
```
MCP Client → FastMCP Server → ExpertRegistry (4 experts)
                            → LLMRouter (LiteLLM → 3 models)
                              → SimpleCache (opt-in)
```

## Expert IDs
architect reviewer security python

## MCP tools
- `list_experts` — list/search experts
- `consult_expert` — query single expert
- `consult_multiple_experts` — parallel expert queries
- `get_expert_prompt` — view system prompt

## Config
`.env` for API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY.
At least one API key required — server fails fast at startup if missing.

Optional: `FALLBACK_MODELS` (comma-separated fallback chain), `LLM_MAX_CONCURRENT=4`.
LLM resilience: `LLM_MAX_RETRIES=2`, `LLM_RETRY_BASE_DELAY_SECONDS=0.5`, `LLM_TIMEOUT_SECONDS=90`.
