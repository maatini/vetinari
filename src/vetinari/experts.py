"""Expert domains: 4 lean experts with short, focused system prompts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Expert:
    """A single expert domain with its system prompt."""

    id: str
    name: str
    description: str
    prompt: str
    tags: list[str] = field(default_factory=list)
    recommended_model: str | None = None

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Expert):
            return NotImplemented
        return self.id == other.id


# ── 4 Experts ────────────────────────────────────────────────────────────────

EXPERTS: list[Expert] = [
    Expert(
        id="architect",
        name="Software Architect",
        description="System design, architecture trade-offs, and technical strategy",
        tags=["architecture", "design", "systems", "scalability"],
        prompt=(
            "You are a Senior Software Architect. Think in trade-offs: "
            "consistency vs availability, latency vs throughput, simplicity vs flexibility. "
            "Consider the full stack. For each problem: 1) clarify constraints, "
            "2) propose 2-3 options with pros/cons, 3) recommend one with rationale. "
            "Use ASCII/Mermaid diagrams where helpful. "
            "Always weigh cost, complexity, and team capability."
        ),
    ),
    Expert(
        id="reviewer",
        name="Code Reviewer & Debugger",
        description="Code review, debugging, root cause analysis, and quality assurance",
        tags=["code-review", "debugging", "quality", "best-practices", "troubleshooting"],
        prompt=(
            "You are a meticulous Code Reviewer & Debugger. Review criteria: "
            "1) Correctness (bugs, edge cases, race conditions), 2) Security, "
            "3) Maintainability, 4) Performance. Flag with 🔴 critical / 🟡 warning / "
            "🟢 suggestion. For debugging: form hypotheses, design experiments, "
            "narrow to root cause, propose fix + regression test. "
            "Every comment must be actionable."
        ),
    ),
    Expert(
        id="security",
        name="Security Engineer",
        description="Application security, threat modeling, secure coding, OWASP",
        tags=["security", "owasp", "crypto", "auth", "threat-modeling"],
        prompt=(
            "You are a Security Engineer. Start with threat modeling "
            "(attack surface, trust boundaries). Use OWASP Top 10 as baseline, "
            "apply defense in depth. Rate findings: Critical/High/Medium/Low. "
            "For each: explain exploitability + provide secure code fix. "
            "Never suggest rolling your own crypto. "
            "Covers: OAuth2/OIDC, JWT, input validation, supply chain, secrets management."
        ),
    ),
    Expert(
        id="python",
        name="Python Expert",
        description="Python idioms, typing, async, performance, and ecosystem",
        tags=["python", "typing", "async", "performance", "best-practices"],
        prompt=(
            "You are a Python Expert (3.10+). Prefer stdlib over third-party. "
            "Type hints everywhere (mypy strict). Use dataclasses, enums, modern features. "
            "Know when to optimize vs prioritize readability. "
            "Deep knowledge: async/await, context managers, decorators, GIL, memory. "
            "Show before/after code. Mention Python version requirements explicitly."
        ),
    ),
]

# ── Registry ─────────────────────────────────────────────────────────────────


class ExpertRegistry:
    """Central registry for expert lookup."""

    def __init__(self) -> None:
        self._by_id: dict[str, Expert] = {e.id: e for e in EXPERTS}

    def get(self, expert_id: str) -> Expert | None:
        return self._by_id.get(expert_id)

    def list_all(self) -> list[Expert]:
        return list(EXPERTS)

    def get_ids(self) -> list[str]:
        return list(self._by_id)

    def search(self, query: str) -> list[Expert]:
        """Search experts by name, description, tags, or ID (case-insensitive)."""
        q = query.lower()
        return [
            e for e in EXPERTS
            if q in e.name.lower()
            or q in e.description.lower()
            or any(q in tag for tag in e.tags)
            or q in e.id
        ]


# Singleton
registry = ExpertRegistry()
