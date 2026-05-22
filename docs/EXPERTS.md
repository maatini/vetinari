# Expertendokumentation

## Übersicht der 11 Experten-Domänen

| ID | Name | Tags | Empfohlenes Modell |
|----|------|------|-------------------|
| `architect` | Software Architect | architecture, design, systems, patterns, scalability | claude-3-5-sonnet |
| `code-reviewer` | Senior Code Reviewer | code-review, quality, best-practices, security | claude-3-5-sonnet |
| `python-expert` | Python Expert | python, typing, async, performance, best-practices | gpt-4o-mini |
| `devops` | DevOps / Platform Engineer | devops, ci-cd, docker, kubernetes, cloud, terraform | gpt-4o-mini |
| `security` | Cybersecurity Analyst | security, owasp, crypto, auth, threat-modeling | claude-3-5-sonnet |
| `data-engineer` | Data Engineer | data, sql, etl, pipeline, analytics, warehouse | gpt-4o-mini |
| `ml-engineer` | ML/AI Engineer | ml, ai, llm, mlops, deep-learning, transformers | gpt-4o-mini |
| `frontend` | Frontend Engineer | frontend, react, typescript, css, a11y, performance | gpt-4o-mini |
| `rustacean` | Rust Engineer | rust, systems, performance, safety, embedded | claude-3-5-sonnet |
| `debugger` | Debugging Specialist | debugging, troubleshooting, performance, profiling | claude-3-5-sonnet |
| `product-manager` | Technical Product Manager | product, strategy, planning, stakeholders, roadmap | gpt-4o-mini |

## Detaillierte Beschreibungen

### Software Architect
- System-Design, Architektur-Patterns, Technologie-Strategie
- Denkweise: Trade-offs, Full-Stack, Constraints-first
- Stil: Präzise, strukturiert, ASCII/Mermaid-Diagramme

### Senior Code Reviewer
- Code-Qualität, Security-Review, Best Practices
- Kriterien: Korrektheit > Security > Wartbarkeit > Performance > Stil
- Stil: 🔴🟡🟢 Prioritäten, pro Kommentar: Was, Warum, Fix

### Python Expert
- Python 3.12+, Typing, Async, Performance
- Kernprinzipien: stdlib first, mypy-strict, dataclasses/modern features
- Stil: Code-first, Before/After, explizite Versionsangaben

### DevOps / Platform Engineer
- CI/CD, IaC, Container, Kubernetes, Cloud
- Philosophie: Reproduzierbarkeit, Observability, Security-by-design
- Stil: YAML/TOML/HCL Snippets, Kosten-Implikationen

### Cybersecurity Analyst
- AppSec, Threat Modeling, OWASP, Kryptographie
- Methodologie: Attack-Surface > Defense-in-depth > Assume breach
- Stil: Critical/High/Medium/Low Ratings, Exploitability + Code-Beispiele

### Data Engineer
- Data Pipelines, SQL, ETL, Data Warehousing
- Prinzipien: Idempotency, Schema Evolution, Data Quality
- Stil: SQL/DDL, Mermaid-Diagramme, Governance

### ML/AI Engineer
- ML, Deep Learning, MLOps, LLM Integration
- Mindset: Deploy > Baseline > Data Quality > Model Architecture
- Stil: Code-Snippets, Compute Requirements, Evaluation

### Frontend Engineer
- React, TypeScript, CSS, Performance, Accessibility
- Werte: a11y ≥ WCAG 2.1 AA, Core Web Vitals, Semantic HTML
- Stil: Component Code + Types, a11y Notes, Browser-Kompatibilität

### Rust Engineer
- Rust Internals, Ownership, Async, Embedded
- Philosophie: Compiler-driven correctness, Zero-cost abstractions
- Stil: Cargo.toml, Lifetime-Annotationen, SAFETY-Kommentare

### Debugging Specialist
- Systematisches Debugging, Root Cause Analysis
- Methode: Reproduzieren > Hypothesen > Experimente > Root Cause > Fix
- Tools: git bisect, Profiling, Log-Analyse, Netzwerk-Debugging

### Technical Product Manager
- Produktstrategie, Roadmaps, Stakeholder-Alignment
- Framework: WHY-first, Success Metrics, MVP > Polish
- Stil: Strukturiert, Tabellen, Fakten vs. Annahmen

## Modell-Empfehlung

| Use Case | Empfohlenes Modell |
|----------|-------------------|
| Code-Review, Security, Architektur | claude-3-5-sonnet |
| Python, Frontend, DevOps, Data, ML | gpt-4o-mini |
| Rust, Debugging | claude-3-5-sonnet |
| Product Management | gpt-4o-mini |

## Neuen Experten hinzufügen

```python
# In src/expert_advisor/experts/prompts.py
Expert(
    id="dein-experte",
    name="Name",
    description="Beschreibung",
    prompt="""Detaillierter System-Prompt...""",
    tags=["tag1", "tag2"],
    recommended_model="gpt-4o-mini",
)
```

Der Experte wird automatisch von der Registry erkannt — keine weitere Konfiguration nötig.
