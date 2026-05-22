# Architektur — Multi-LLM Expert Advisor

## Komponenten-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Client (pi, DeepSeek TUI)            │
└────────────────────────────┬────────────────────────────────┘
                             │ JSON-RPC (stdio/http)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastMCP Server (server.py)                 │
│                                                              │
│  Tools:                                                      │
│  • list_experts        • search_experts                      │
│  • consult_expert      • consult_multiple_experts            │
│  • cost_summary        • get_expert_prompt                   │
└───────┬──────────────────────────────────┬──────────────────┘
        │                                  │
        ▼                                  ▼
┌───────────────┐                  ┌──────────────────┐
│   Registry    │                  │   LLM Router     │
│  (experts/)   │                  │  (routers/)      │
│               │                  │                   │
│ • 11 Experts  │                  │ • LiteLLM API     │
│ • Search      │                  │ • Fallback Logic  │
│ • Tags        │                  │ • TTLCache        │
└───────────────┘                  │ • RateLimiter     │
                                   │ • CostTracker     │
                                   └────────┬─────────┘
                                            │
                                   ┌────────┴─────────┐
                                   │   LiteLLM        │
                                   │                   │
                                   │ OpenAI | Anthropic│
                                   │ Google | DeepSeek │
                                   │ Groq              │
                                   └───────────────────┘
```

## Datenfluss: `consult_expert`

```
1. Client ruft consult_expert(expert_id="architect", query="...")
2. Server holt Expert aus Registry
3. Router.builds System-Prompt (expert.prompt + user query)
4. Cache-Check → Cache-Hit? Direkt zurück
5. Cache-Miss → Model-Selektion:
   a. Expert.recommended_model oder default
   b. API-Key prüfen
   c. Rate-Limit prüfen
   d. litellm.acompletion() aufrufen
   e. Bei Fehler: next model (Fallback) + Exponential Backoff
6. Erfolg → Cache speichern, CostTracker updaten
7. ExpertAdviceResponse → JSON → Client
```

## Fehlerbehandlung

```
Primary Model (gpt-4o-mini)
    ├── API-Key fehlt? → Fallback 1 (claude-3-5-sonnet)
    ├── Rate-Limit?    → Fallback 2 (gemini-2.0-flash)
    ├── API-Error?     → Fallback 3 (deepseek-chat)
    │                     ...
    └── Alle failed    → ExpertAdviceResponse(error="All models failed")
```

Retry-Strategie: Exponential Backoff (1s → 2s → 4s → ... → max 30s).

## Rate Limiting

Sliding-Window pro Modell:
- Default: 30 requests / 60 seconds
- Separate Limits pro Modell (deepseek ≠ gpt-4o)
- Konfigurierbar via `RATE_LIMIT_WINDOW_SECONDS` / `RATE_LIMIT_MAX_REQUESTS`

## Caching

TTL-basierter In-Memory Cache:
- Key: SHA-256 des vollständigen Prompts
- TTL: 300s (konfigurierbar via `CACHE_TTL_SECONDS`)
- Max Entries: 1000 (LRU Eviction bei Überlauf)
- Cache-Hits zählen nicht zum Budget-Limit

## Kosten-Tracking

```python
CostTracker:
  - total_cost        # Kumulierte Kosten aller Calls
  - total_tokens      # Gesamt-Tokens
  - breakdown         # pro Modell: {"gpt-4o-mini": 0.001, ...}
  - cached_calls      # Anzahl Cache-Hits
  - failed_calls      # Anzahl fehlgeschlagener Calls
```

Budget-Warnung per Log bei Überschreitung von `BUDGET_WARNING_THRESHOLD`.
Hard-Limit möglich via `BUDGET_LIMIT`.

## Konfiguration

Alle Einstellungen via `pydantic-settings`:
- `.env` Datei (automatisch geladen)
- Environment Variables (override .env)
- Defaults in `config.py`

| Variable | Default | Beschreibung |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |
| `LOG_LEVEL` | INFO | Logging Level |
| `DEFAULT_MODEL` | gpt-4o-mini | Standard-Modell |
| `CACHE_TTL_SECONDS` | 300 | Cache TTL |
| `RATE_LIMIT_MAX_REQUESTS` | 30 | Rate Limit pro Minute |
| `BUDGET_WARNING_THRESHOLD` | 5.0 | Budget-Warnung bei $ |
