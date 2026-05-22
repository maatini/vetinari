# Multi-LLM Expert Advisor — MCP Server

> Intelligenter Multi-Expert-Advisor für MCP-fähige Agentic TUIs wie pi, DeepSeek TUI, Cursor, Claude Code.

## Features

- **11 Expertendomänen:** Software Architect, Code Reviewer, Python Expert, DevOps, Security Analyst, Data Engineer, ML/AI Engineer, Frontend Engineer, Rust Engineer, Debugging Specialist, Technical Product Manager
- **5+ LLM Provider:** OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude 3.5 Sonnet), Google (Gemini), DeepSeek, Groq — via LiteLLM
- **Fallback & Resilienz:** Automatisches Fallback bei API-Fehlern, Retry mit Exponential Backoff
- **Rate Limiting:** Sliding-Window pro Modell
- **Caching:** In-Memory TTL-Cache zur Kosten- und Latenzreduktion
- **Kosten-Tracking:** Detailliertes Usage-Tracking pro Modell, Budget-Warnungen
- **Parallele Beratung:** Mehrere Experten gleichzeitig per `asyncio.gather`

## Quick Start

### 1. Devbox-Umgebung

```bash
devbox shell
uv sync
```

### 2. API Keys konfigurieren

```bash
cp .env.example .env
# Edit .env mit deinen API Keys
```

### 3. Server testen

```bash
devbox run server
```

### 4. Tests ausführen

```bash
devbox run test-cov
```

## MCP Integration

In `.mcp.json` deines Projekts:

```json
{
  "mcpServers": {
    "multi-llm-vetinari": {
      "command": "uv",
      "args": ["run", "python", "-m", "expert_advisor.server"],
      "cwd": "/pfad/zu/multi-llm-vetinari"
    }
  }
}
```

## Tools

### `list_experts`
Alle verfügbaren Experten auflisten.

```json
// Input
{ "query": "python" }  // Optional: Filter

// Output
[
  {
    "id": "python-expert",
    "name": "Python Expert",
    "description": "Python language expert: idioms, typing, async, performance",
    "tags": ["python", "typing", "async", "performance"],
    "recommended_model": "gpt-4o-mini"
  }
]
```

### `consult_expert`
Einen Experten zu einem Thema befragen.

```json
// Input
{
  "expert_id": "architect",
  "query": "How to design a rate-limited API?",
  "model": null,       // Optional: Modell auswählen
  "temperature": 0.7
}

// Output
{
  "success": true,
  "expert_id": "architect",
  "expert_name": "Software Architect",
  "model_used": "gpt-4o-mini",
  "content": "...",
  "usage": {
    "prompt_tokens": 500,
    "completion_tokens": 300,
    "total_tokens": 800,
    "cost_usd": 0.00015
  },
  "fallback_used": false,
  "retrieval_time_ms": 1200.5
}
```

### `consult_multiple_experts`
Mehrere Experten parallel befragen.

```json
// Input
{
  "expert_ids": ["architect", "security"],
  "query": "Design a secure authentication system"
}
```

### `cost_summary`
Kumulierte Kosten-Statistiken.

### `search_experts`
Experten per Suchbegriff finden.

### `get_expert_prompt`
System-Prompt eines Experten abrufen.

## Architektur

```
src/expert_advisor/
├── config.py          # pydantic-settings Konfiguration
├── server.py          # FastMCP Server mit Tool-Definitionen
├── experts/
│   ├── prompts.py     # 11 Experten mit System-Prompts
│   └── registry.py    # Zentrale Expertensuche
├── routers/
│   └── llm_router.py  # LiteLLM Wrapper, Fallback, Cache, Rate Limiting
└── utils/
    ├── logging.py     # structlog Konfiguration
    └── cost_tracker.py # Kosten- und Token-Tracking
```

## Development

```bash
# Dev-Setup
devbox shell
uv sync

# Tests
uv run pytest -q
uv run pytest --cov=src/expert_advisor --cov-report=term-missing -q

# Linting
uv run ruff check src/ tests/

# Demo
uv run python examples/basic_usage.py
```
