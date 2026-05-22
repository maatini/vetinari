# MCP-Integration — Multi-LLM Expert Advisor

## pi (TUI Coding Agent)

In `.mcp.json`:

```json
{
  "mcpServers": {
    "multi-llm-vetinari": {
      "command": "uv",
      "args": ["run", "python", "-m", "expert_advisor.server"],
      "cwd": "/Volumes/SSD2TB/work/antigravity/vetinary",
      "lifecycle": "lazy",
      "idleTimeout": 15
    }
  }
}
```

Verwendung innerhalb pi:
- `/mcp multi-llm-vetinari list-experts` — Experten anzeigen
- `/mcp multi-llm-vetinari consult-expert --expert_id architect --query "..."` — Experten befragen

## Beispiel-Prompts für pi

```
"Befrage den security-Experten zu meiner JWT-Implementierung"
"Lass den code-reviewer diesen PR reviewen"
"Frage mehrere Experten: architect + devops — wie deployen?"
"Hole mir vom python-expert feedback zu dieser async-Funktion"
```

## DeepSeek TUI

Mit dem MCP-Plugin `mcp-deepseek`:

```yaml
# config.yaml
mcp_servers:
  multi-llm-vetinari:
    command: uv
    args: ["run", "python", "-m", "expert_advisor.server"]
    cwd: /Volumes/SSD2TB/work/antigravity/vetinary
```

## Cursor / Claude Code

In Cursor/Claude Code MCP-Settings:

```json
{
  "mcpServers": {
    "expert-advisor": {
      "command": "uv",
      "args": ["run", "python", "-m", "expert_advisor.server"],
      "cwd": "/path/to/multi-llm-vetinari"
    }
  }
}
```

## Allgemeine Hinweise

- Der Server läuft im `lazy`-Modus: Start nur bei Bedarf, Stop nach 15s Idle
- Alle Tools geben JSON zurück (für maschinelle Weiterverarbeitung geeignet)
- `consult_expert` und `consult_multiple_experts` sind async und blockieren nicht
