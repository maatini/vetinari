# Multi-LLM Expert Advisor — pi context

## Project
MCP server that provides intelligent multi-expert advisory via LLMs.
11 expert domains, LiteLLM routing, FastMCP server.

## Quick commands
- `devbox run test` — run tests
- `devbox run test-cov` — tests with coverage
- `devbox run server` — start MCP server
- `devbox run demo` — run usage examples
- `uv run ruff check src/ tests/` — lint
- `uv run python examples/basic_usage.py` — non-LLM demo

## Key files
- `src/expert_advisor/server.py` — FastMCP server with 6 tools
- `src/expert_advisor/routers/llm_router.py` — LiteLLM wrapper (fallback, cache, rate limit)
- `src/expert_advisor/experts/prompts.py` — 11 expert system prompts
- `src/expert_advisor/experts/registry.py` — expert lookup
- `src/expert_advisor/config.py` — pydantic-settings config
- `src/expert_advisor/utils/cost_tracker.py` — cost/token tracking
- `src/expert_advisor/utils/logging.py` — structlog config
- `tests/` — 57 tests, 91% coverage
- `docs/ARCHITECTURE.md` — component overview
- `docs/EXPERTS.md` — expert descriptions
- `docs/INTEGRATION.md` — MCP client setup

## Architecture
```
MCP Client → FastMCP Server → ExpertRegistry (11 experts)
                            → LLMRouter (LiteLLM → 6 models, 5 providers)
                              → TTLCache, RateLimiter, CostTracker
```

## Expert IDs
architect code-reviewer python-expert devops security data-engineer
ml-engineer frontend rustacean debugger product-manager

## MCP tools
- `list_experts` — list all experts
- `consult_expert` — query single expert
- `consult_multiple_experts` — parallel expert queries
- `cost_summary` — cumulative costs
- `search_experts` — search by name/tag
- `get_expert_prompt` — view system prompt

## Config
`.env` for API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY, GROQ_API_KEY.
At least one API key required for LLM calls.
