# Expert Advisor — Lean MCP Server

> Simple multi-expert MCP server for Cursor, Claude Code, and pi.  
> 4 experts, LiteLLM routing, parallel consultation. No bloat.

## Why?

Instead of asking a single LLM, get **4 specialized perspectives** in parallel on system design, code quality, security, and Python — all through one MCP server.

## Quick Start

```bash
# 1. Set up environment
devbox shell

# 2. Add at least one API key
cp .env.example .env  # Edit: OPENAI_API_KEY or ANTHROPIC_API_KEY or DEEPSEEK_API_KEY

# 3. Start server
devbox run server
```

## MCP Integration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "expert-advisor": {
      "command": "uv",
      "args": ["run", "python", "-m", "expert_advisor.server"],
      "cwd": "/path/to/vetinary"
    }
  }
}
```

## MCP Tools

| Tool | Description |
|---|---|
| `list_experts` | List/search all experts |
| `consult_expert` | Query a single expert |
| `consult_multiple_experts` | Query multiple experts in parallel ⚡ |
| `get_expert_prompt` | View an expert's system prompt |

## Features

- **LiteLLM routing** — primary model + automatic fallback (3 models)
- **Parallel consultation** — `asyncio.gather` across multiple experts
- **3 models**: Claude 3.5 Sonnet, GPT-4o-mini, DeepSeek Chat
- **Optional cache** — set `ENABLE_CACHE=true` in `.env`
- **Minimal cost log** — `total_tokens` + `total_cost`, nothing more

## Config (.env)

```bash
# At least one API key
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...

# Optional
DEFAULT_MODEL=gpt-4o-mini
ENABLE_CACHE=false
```

## Dev

```bash
devbox shell             # Enter dev environment
devbox run test          # Run tests
devbox run test-cov      # Tests + coverage
devbox run lint          # Ruff
```
