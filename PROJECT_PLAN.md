# Multi-LLM-Expert-Advisor MCP Server — Projektplan

> **Projektname:** `multi-llm-vetinari`
> **Ziel:** Ein professioneller, erweiterbarer MCP-Server, der als intelligenter Multi-Expert-Advisor für DeepSeek-TUI (und andere MCP-fähige Agentic TUIs/IDEs) dient.

---

## 1. Projekt-Überblick & Ziele

**Hauptziele:**
- Hochqualitativer, wartbarer MCP-Server für Experten-Beratung
- Unterstützung mehrerer LLMs mit intelligentem Routing
- Sehr gute Antwortqualität durch spezialisierte System-Prompts
- Einfache Erweiterbarkeit (neue Experten + neue Provider)
- Vollständige Reproduzierbarkeit durch Devbox
- Produktionsreif (Fehlerbehandlung, Logging, Fallbacks)

**Erfolgsmetriken:**
- Mindestens 8 Experten-Domänen
- Mindestens 5 verschiedene LLM-Provider
- Automatisches Fallback + Kosten-Tracking
- Saubere Dokumentation + Beispiele

---

## 2. Technologie-Stack (Devbox)

| Komponente              | Version / Tool          | Begründung                     |
|-------------------------|-------------------------|--------------------------------|
| Python                  | 3.12                    | Aktuell & stabil               |
| Package Manager         | `uv`                    | Extrem schnell                 |
| MCP Framework           | `mcp[cli]` + FastMCP    | Offiziell & einfach            |
| LLM Abstraktion         | `litellm`               | Unterstützt fast alle Provider |
| Dev Environment         | **Devbox** (Nix)        | Reproduzierbar                 |
| Typing & Validation     | `pydantic` + `dataclasses` | Typsicherheit               |
| Async                   | `asyncio` + `httpx`     | Performance                    |
| Logging & Observability | `structlog` + `rich`    | Professionelles Logging        |
| Testing                 | `pytest` + `pytest-asyncio` | Gute Testabdeckung          |
| Konfiguration           | `pydantic-settings`     | Saubere Config                 |

---

## 3. Ordnerstruktur

```
multi-llm-vetinari/
├── devbox.json
├── devbox.lock
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── README.md
├── PROJECT_PLAN.md
├── src/
│   └── expert_advisor/
│       ├── __init__.py
│       ├── server.py              # Haupt-MCP-Server
│       ├── config.py              # pydantic-settings Konfiguration
│       ├── experts/
│       │   ├── __init__.py
│       │   ├── registry.py        # Zentrale Expert-Registry
│       │   └── prompts.py         # System-Prompts aller Experten
│       ├── routers/
│       │   ├── __init__.py
│       │   └── llm_router.py      # LiteLLM Wrapper + Fallback
│       └── utils/
│           ├── __init__.py
│           ├── logging.py         # structlog Konfiguration
│           └── cost_tracker.py    # Kosten-Tracking
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_registry.py
│   ├── test_router.py
│   └── test_server.py
├── docs/
│   ├── EXPERTS.md
│   └── ARCHITECTURE.md
└── examples/
    └── basic_usage.py
```

---

## 4. Phasenplan

### Phase 0: Devbox-Umgebung aufsetzen (2 Std)
- [x] Verzeichnis anlegen
- [x] `devbox init` / `devbox.json` erstellen
- [x] `devbox shell` → Umgebung testen
- [x] `uv init` + Dependencies installieren
- [x] `.gitignore` + `.env.example` anlegen
- [x] Git-Repository initialisieren

### Phase 1: Projekt-Scaffolding & Struktur (3 Std)
- [x] Alle Pakete in `pyproject.toml`
- [x] `src/expert_advisor/` Ordnerstruktur
- [x] `config.py` mit pydantic-settings
- [x] Basis-Logging mit structlog
- [x] `__init__.py` in allen Paketen

### Phase 2: Expert Registry & Domänen-Modell (4 Std)
- [x] `Expert` Dataclass
- [x] Mindestens 10 Experten definieren (11)
- [x] Detaillierte System-Prompts
- [x] `list_experts()` Tool

### Phase 3: Core MCP Server & Tool-Definition (5 Std)
- [x] `server.py` mit FastMCP
- [x] Tool `consult_expert` implementieren
- [x] Automatische Modellauswahl
- [x] Strukturierte Rückgabe (ExpertAdviceResponse)

### Phase 4: Multi-LLM Integration mit LiteLLM (6 Std)
- [x] `llm_router.py` erstellen
- [x] LiteLLM konfigurieren (6 Modelle, 5 Provider)
- [x] Fallback-Mechanismus
- [x] Kosten-Tracking via litellm.completion_cost

### Phase 5: Erweiterte Features (7 Std)
- [x] `consult_multiple_experts` (parallel via asyncio.gather)
- [x] Cost & Token Tracking (CostTracker)
- [x] Caching (In-Memory, TTL-basiert)
- [x] Rate Limiting (Sliding Window) & Retry (Exponential Backoff)
- [x] Structured Output (ExpertAdviceResponse, UsageInfo)
- [x] Logging aller Anfragen (structlog)

### Phase 6: Testing & Qualitätssicherung (5 Std)
- [x] Unit Tests (Registry, Router, Config, Cache, CostTracker)
- [x] Integration Tests (mit Mocking, Server-Tools)
- [x] Fallback-Tests (Auth-Error, Retry, Rate-Limit)
- [x] Cost-Tracking-Tests (Aufschlüsselung, Cached/Failed)
- [x] **157 Tests, 89% Coverage**

### Phase 7: Dokumentation & Beispiele (4 Std)
- [x] `README.md` (ausführlich: Features, Quick Start, API-Referenz, Beispiele)
- [x] `docs/EXPERTS.md` (alle 11 Domänen mit Details)
- [x] `docs/ARCHITECTURE.md` (Komponenten, Datenfluss, Fehlerbehandlung)
- [x] `docs/INTEGRATION.md` (pi, DeepSeek TUI, Cursor, Claude Code)
- [x] `examples/basic_usage.py` (7 Anwendungsbeispiele)

### Phase 8: DeepSeek-TUI Integration & Demo (3 Std)
- [x] MCP-Einbindungs-Anleitung (`docs/INTEGRATION.md`)
- [x] Beispiel-Prompts für DeepSeek-TUI / pi
- [x] `devbox run demo` Script

---

## 5. Gesamtzeitplan

| Phase | Aufwand     | Priorität | Status |
|-------|-------------|-----------|--------|
| 0     | 2 Std       | Hoch      | ✅     |
| 1     | 3 Std       | Hoch      | ✅     |
| 2     | 4 Std       | Hoch      | ✅     |
| 3     | 5 Std       | Hoch      | ✅     |
| 4     | 6 Std       | Hoch      | ✅     |
| 5     | 7 Std       | Mittel    | ✅     |
| 6     | 5 Std       | Hoch      | ✅     |
| 7     | 4 Std       | Mittel    | ✅     |
| 8     | 3 Std       | Mittel    | ✅     |
| **Gesamt** | **~39 Stunden** | — | ✅     |

