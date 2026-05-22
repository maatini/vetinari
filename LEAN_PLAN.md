# LEAN PLAN — Simplification Roadmap

> Ziel: Vollwertiger Produktions-Proxy → einfacher MCP-Server für persönliche Nutzung
> Prinzip: „Weniger ist mehr" – 4 Experten, 2-3 Modelle, kein Overhead

## Phase 0: Vorbereitung ✅
- [x] Branch `lean-simplification`
- [x] Tag `v0.1-overengineered`
- [x] LEAN_PLAN.md

## Phase 1: Experten radikal reduzieren (4 statt 11)
Behalten: architect, reviewer (kombiniert code-reviewer + debugger), security, python
Löschen: devops, data-engineer, ml-engineer, frontend, rustacean, product-manager, debugger
Prompts auf ~350 Zeichen kürzen

## Phase 2: Features vereinfachen
- Rate Limiting: entfernen
- TTL-Cache: optional (enable_cache: bool = False)
- Cost-Tracking: nur total_tokens + total_cost loggen
- Modelle: 3 Modelle (claude-3-5-sonnet + gpt-4o-mini + deepseek-chat)
- Fallback: Primary → Fallback (statt 6 Modelle)

## Phase 3: Code-Refactoring
```
src/expert_advisor/
├── server.py          # Tools + FastMCP Setup
├── experts.py         # 4 Experten + Registry (eine Datei!)
├── llm.py             # LiteLLM-Wrapper (stark vereinfacht)
├── config.py          # kleinere Config
└── utils/
    └── logging.py
```
Löschen: routers/ Ordner, cost_tracker.py
Globale router-Instanz → Dependency Injection

## Phase 4: MCP-Tools aufräumen
- list_experts + search_experts → list_experts(query?: str)
- consult_expert, consult_multiple_experts → behalten
- get_expert_prompt → behalten
- cost_summary → optional/vereinfacht

## Phase 5: Doku & Beispiele
- README.md neu schreiben (Quick Start, 3 Zeilen)
- examples/basic_usage.py stark vereinfachen
- CLAUDE.md, PROJECT_PLAN.md anpassen
