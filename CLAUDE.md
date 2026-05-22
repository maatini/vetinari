# Expert Advisor — pi context

## Project
MCP server: 4 expert advisors via LLMs. LiteLLM routing, FastMCP, parallel consultation.

## Quick commands
- `devbox run test` — run tests
- `devbox run test-cov` — tests with coverage
- `devbox run server` — start MCP server
- `devbox run demo` — run usage examples
- `uv run ruff check src/ tests/` — lint

## Key files
- `src/expert_advisor/server.py` — FastMCP server with 5 tools
- `src/expert_advisor/llm.py` — LiteLLM wrapper (fallback, optional cache, cost log)
- `src/expert_advisor/experts.py` — 4 experts + registry
- `src/expert_advisor/config.py` — pydantic-settings config
- `tests/` — 51 tests

## Architecture
```
MCP Client → FastMCP Server → ExpertRegistry (4 experts)
                            → LLMRouter (LiteLLM → 3 models)
                              → SimpleCache (opt-in), CostLog
```

## Expert IDs
architect reviewer security python

## MCP tools
- `list_experts` — list/search experts
- `consult_expert` — query single expert
- `consult_multiple_experts` — parallel expert queries
- `cost_summary` — cumulative cost/token log
- `get_expert_prompt` — view system prompt

## Config
`.env` for API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY.
At least one API key required.
