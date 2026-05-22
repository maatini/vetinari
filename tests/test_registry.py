"""Tests for Expert Registry (4 experts)."""

from __future__ import annotations

from expert_advisor.experts import Expert, ExpertRegistry, registry


class TestRegistry:
    """Tests for ExpertRegistry."""

    def test_registry_exists(self) -> None:
        assert registry is not None
        assert isinstance(registry, ExpertRegistry)

    def test_four_experts_loaded(self) -> None:
        assert len(registry.list_all()) == 4

    def test_get_by_id(self) -> None:
        architect = registry.get("architect")
        assert architect is not None
        assert architect.name == "Software Architect"

    def test_get_nonexistent(self) -> None:
        assert registry.get("nonexistent") is None

    def test_search_by_name(self) -> None:
        results = registry.search("python")
        assert len(results) == 1
        assert results[0].id == "python"

    def test_search_by_tag(self) -> None:
        results = registry.search("security")
        assert len(results) >= 1
        assert any(e.id == "security" for e in results)

    def test_search_no_results(self) -> None:
        assert len(registry.search("xyzzyblarg")) == 0

    def test_get_ids(self) -> None:
        ids = registry.get_ids()
        assert len(ids) == 4
        assert "architect" in ids
        assert "reviewer" in ids
        assert "security" in ids
        assert "python" in ids

    def test_search_case_insensitive(self) -> None:
        results = registry.search("PYTHON")
        assert len(results) == 1

    def test_all_experts_have_prompts(self) -> None:
        for expert in registry.list_all():
            assert expert.prompt, f"Expert {expert.id} has empty prompt"
            assert len(expert.prompt) > 50, f"Expert {expert.id} prompt too short"

    def test_all_experts_have_tags(self) -> None:
        for expert in registry.list_all():
            assert len(expert.tags) >= 1, f"Expert {expert.id} has no tags"

    def test_expert_hash_and_eq(self) -> None:
        e1 = registry.get("architect")
        e2 = Expert(id="architect", name="X", description="X", prompt="X")
        assert e1 == e2
        assert hash(e1) == hash(e2)

    def test_expert_ids_unique(self) -> None:
        ids = [e.id for e in registry.list_all()]
        assert len(ids) == len(set(ids))

    def test_required_experts_exist(self) -> None:
        required = ["architect", "reviewer", "security", "python"]
        for rid in required:
            assert registry.get(rid) is not None, f"Missing expert: {rid}"

    def test_removed_experts_absent(self) -> None:
        removed = [
            "devops", "data-engineer", "ml-engineer", "frontend",
            "rustacean", "debugger", "product-manager", "code-reviewer",
        ]
        for rid in removed:
            assert registry.get(rid) is None, f"Unexpected expert: {rid}"

    def test_architect_prompt_length(self) -> None:
        """Prompts should be concise (~350-400 chars)."""
        for expert in registry.list_all():
            assert len(expert.prompt) < 600, (
                f"Expert {expert.id} prompt too long: {len(expert.prompt)}"
            )
