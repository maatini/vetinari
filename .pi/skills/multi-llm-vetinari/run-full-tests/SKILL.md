---
description: Führt die komplette Test-Suite mit Coverage aus
---

# Skill: Run Full Test Suite

Führe immer die komplette Test-Suite mit Coverage aus.

**Befehle:**
1. `uv run pytest --cov=src/vetinari --cov-report=term-missing -q`
2. Prüfe, ob Coverage ≥ 85 %
3. Bei Fehlern: Analysiere und schlage Fixes vor
4. Aktualisiere `STATE.md` mit aktuellem Coverage-Wert
