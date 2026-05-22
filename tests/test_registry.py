"""Tests for Expert Registry."""

from __future__ import annotations

from expert_advisor.experts.prompts import Expert
from expert_advisor.experts.registry import ExpertRegistry, registry


class TestRegistry:
    """Tests for ExpertRegistry."""

    def test_singleton_exists(self) -> None:
        """The singleton registry should be pre-populated."""
        assert registry is not None
        assert isinstance(registry, ExpertRegistry)

    def test_all_experts_loaded(self) -> None:
        """All 11 experts should be loaded."""
        assert len(registry.list_all()) == 11

    def test_get_by_id(self) -> None:
        """Look up experts by ID."""
        architect = registry.get("architect")
        assert architect is not None
        assert architect.name == "Software Architect"
        assert "architect" in architect.tags or any(
            "design" in t for t in architect.tags
        )

    def test_get_nonexistent(self) -> None:
        """Return None for unknown expert IDs."""
        assert registry.get("nonexistent") is None

    def test_search_by_name(self) -> None:
        """Search should match expert names (case-insensitive)."""
        results = registry.search("python")
        assert len(results) == 1
        assert results[0].id == "python-expert"

    def test_search_by_tag(self) -> None:
        """Search should match tags."""
        results = registry.search("security")
        assert len(results) >= 1
        assert any(e.id == "security" for e in results)

    def test_search_by_description(self) -> None:
        """Search should match description text."""
        results = registry.search("debugging")
        assert len(results) >= 1
        assert any(e.id == "debugger" for e in results)

    def test_search_no_results(self) -> None:
        """Search with nonsense query returns empty."""
        assert len(registry.search("xyzzyblarg")) == 0

    def test_get_ids(self) -> None:
        """get_ids() returns all expert IDs."""
        ids = registry.get_ids()
        assert len(ids) == 11
        assert "architect" in ids
        assert "security" in ids

    def test_search_by_tag_case_insensitive(self) -> None:
        """Tag search should be case-insensitive."""
        results = registry.search("PYTHON")
        assert len(results) == 1

    def test_all_experts_have_prompts(self) -> None:
        """Every expert must have a non-empty system prompt."""
        for expert in registry.list_all():
            assert expert.prompt, f"Expert {expert.id} has empty prompt"
            assert len(expert.prompt) > 100, f"Expert {expert.id} prompt too short"

    def test_all_experts_have_tags(self) -> None:
        """Every expert should have at least one tag."""
        for expert in registry.list_all():
            assert len(expert.tags) >= 1, f"Expert {expert.id} has no tags"

    def test_expert_hash_and_eq(self) -> None:
        """Experts with same ID should be equal."""
        e1 = registry.get("architect")
        e2 = Expert(
            id="architect",
            name="Different",
            description="Different",
            prompt="Different",
        )
        assert e1 == e2
        assert hash(e1) == hash(e2)

    def test_expert_ids_unique(self) -> None:
        """All expert IDs must be unique."""
        ids = [e.id for e in registry.list_all()]
        assert len(ids) == len(set(ids))

    def test_specific_experts_exist(self) -> None:
        """Verify key experts exist."""
        required = [
            "architect",
            "code-reviewer",
            "python-expert",
            "devops",
            "security",
            "data-engineer",
            "ml-engineer",
            "frontend",
            "rustacean",
            "debugger",
            "product-manager",
        ]
        for rid in required:
            assert registry.get(rid) is not None, f"Missing expert: {rid}"


class TestSearchByTag:
    """Tests for search_by_tag method."""

    def test_search_by_tag_returns_experts(self) -> None:
        """search_by_tag should return matching experts."""
        results = registry.search_by_tag("python")
        assert len(results) == 1
        assert results[0].id == "python-expert"

    def test_search_by_tag_nonexistent(self) -> None:
        """Empty list for unknown tags."""
        assert registry.search_by_tag("nonexistent-tag") == []
