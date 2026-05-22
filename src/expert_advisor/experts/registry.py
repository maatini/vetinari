"""Expert Registry — central registry for expert lookup and management."""

from __future__ import annotations

from expert_advisor.experts.prompts import EXPERT_IDS, EXPERTS, Expert


class ExpertRegistry:
    """Central registry for expert lookup by ID or tag."""

    def __init__(self) -> None:
        self._by_id: dict[str, Expert] = {e.id: e for e in EXPERTS}
        self._by_tag: dict[str, list[Expert]] = {}
        for expert in EXPERTS:
            for tag in expert.tags:
                self._by_tag.setdefault(tag, []).append(expert)

    def get(self, expert_id: str) -> Expert | None:
        """Look up an expert by ID."""
        return self._by_id.get(expert_id)

    def search_by_tag(self, tag: str) -> list[Expert]:
        """Find all experts matching a tag (case-insensitive)."""
        return self._by_tag.get(tag.lower(), [])

    def list_all(self) -> list[Expert]:
        """Return all registered experts."""
        return list(EXPERTS)

    def search(self, query: str) -> list[Expert]:
        """Search experts by name, description, or tags (fuzzy)."""
        q = query.lower()
        results: list[Expert] = []
        for expert in EXPERTS:
            if (
                q in expert.name.lower()
                or q in expert.description.lower()
                or any(q in tag for tag in expert.tags)
                or q in expert.id
            ):
                results.append(expert)
        return results

    def get_ids(self) -> list[str]:
        """Return all expert IDs."""
        return list(EXPERT_IDS)


# Singleton instance
registry = ExpertRegistry()
