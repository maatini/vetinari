#!/usr/bin/env python3
"""
setup_skills.py - Korrigierte Version mit YAML-Header
"""

from pathlib import Path
import textwrap
import argparse

SKILLS = {
    "build-expert": {
        "description": "Erstellt detaillierte System-Prompts für neue Experten-Domänen",
        "content": textwrap.dedent("""\
            # Skill: Build Expert

            Du bist Experte für die Erstellung neuer Domänen-Experten im Projekt multi-llm-vetinari.

            **Regeln:**
            - Folge exakt Phase 2 des Projektplans
            - Erstelle sehr detaillierte, einzigartige System-Prompts
            - Jeder Experte bekommt eine klare Persönlichkeit + Denkweisen
            - Verwende Karpathy-Style: klar, strukturiert, mit Beispielen
            - Nach Erstellung: Aktualisiere `src/expert_advisor/experts/prompts.py` und `docs/EXPERTS.md`
        """)
    },

    "run-full-tests": {
        "description": "Führt die komplette Test-Suite mit Coverage aus",
        "content": textwrap.dedent("""\
            # Skill: Run Full Test Suite

            Führe immer die komplette Test-Suite mit Coverage aus.

            **Befehle:**
            1. `uv run pytest --cov=src/expert_advisor --cov-report=term-missing -q`
            2. Prüfe, ob Coverage ≥ 85 %
            3. Bei Fehlern: Analysiere und schlage Fixes vor
            4. Aktualisiere `STATE.md` mit aktuellem Coverage-Wert
        """)
    },

    "reflect-karpathy": {
        "description": "Führt eine Karpathy-Style Reflection nach Aufgaben durch",
        "content": textwrap.dedent("""\
            # Skill: Karpathy-Reflection

            Nach jeder größeren Aufgabe oder Phase führe eine Karpathy-Style Reflection durch:

            1. Was lief gut?
            2. Was war suboptimal?
            3. Passt es 100 % zum Spec?
            4. Wie kann es robuster werden?
            5. Was ist der nächste kleinste sinnvolle Schritt?
        """)
    },

    "update-docs": {
        "description": "Aktualisiert alle relevanten Dokumentationsdateien",
        "content": textwrap.dedent("""\
            # Skill: Update Documentation

            Aktualisiere nach jeder Phase oder größeren Änderung:
            - README.md
            - docs/EXPERTS.md
            - docs/ARCHITECTURE.md
            - STATE.md
        """)
    },

    "create-expert-prompt": {
        "description": "Erstellt hochwertige System-Prompts für neue Experten",
        "content": textwrap.dedent("""\
            # Skill: Create Expert Prompt

            Erstelle einen hochwertigen System-Prompt für einen neuen Experten mit:
            - Klarer Rolle + Persönlichkeit
            - Spezifischen Denkweisen
            - Beispielen für gute Antworten
            - Karpathy-inspirierter Präzision
        """)
    },

    "implement-phase": {
        "description": "Unterstützt bei der Umsetzung einer gesamten Projektphase",
        "content": textwrap.dedent("""\
            # Skill: Implement Phase

            Hilft bei der Umsetzung einer Phase aus dem Projektplan.

            **Vorgehen:**
            1. Lies den aktuellen Stand in STATE.md
            2. Lies die Phase im PROJECT_PLAN.md
            3. Plane atomare Schritte
            4. Implementiere, teste und verifiziere
            5. Führe Karpathy-Reflection durch
        """)
    },

    "verify-mcp": {
        "description": "Prüft, ob der MCP-Server korrekt läuft",
        "content": textwrap.dedent("""\
            # Skill: Verify MCP Server

            Prüfe, ob der MCP-Server korrekt läuft und alle Tools verfügbar sind.
        """)
    },
}


def create_skills_directory(base_path: Path) -> Path:
    skills_dir = base_path / ".pi" / "skills" / "multi-llm-vetinari"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def write_skill(skills_dir: Path, name: str, skill_data: dict, force: bool = False) -> bool:
    skill_dir = skills_dir / name
    skill_dir.mkdir(exist_ok=True)
    skill_file = skill_dir / "SKILL.md"

    if skill_file.exists() and not force:
        print(f"⚠️  Überspringe (existiert bereits): {name}")
        return False

    # WICHTIG: YAML-Header mit description
    header = f"---\ndescription: {skill_data['description']}\n---\n\n"
    full_content = header + skill_data['content'].strip() + "\n"

    skill_file.write_text(full_content, encoding="utf-8")
    print(f"✅ Erstellt: .pi/skills/multi-llm-vetinari/{name}/SKILL.md")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Überschreibt existierende Skills")
    args = parser.parse_args()

    project_root = Path(__file__).parent.resolve()
    skills_dir = create_skills_directory(project_root)

    print(f"\n📁 Zielverzeichnis: {skills_dir}")
    print("─" * 60)

    created = 0
    for name, data in SKILLS.items():
        if write_skill(skills_dir, name, data, force=args.force):
            created += 1

    print("─" * 60)
    print(f"🎉 Fertig! {created} Skills wurden erstellt/aktualisiert.\n")
    print("Starte Pi neu und teste mit:")
    print("  /skill multi-llm-vetinari/build-expert")


if __name__ == "__main__":
    main()

