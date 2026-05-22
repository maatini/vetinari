#!/usr/bin/env python3
"""Basic usage examples for the Expert Advisor (Lean Edition).

Run with: uv run python examples/basic_usage.py
"""

from expert_advisor.experts import registry


def show_experts():
    """List all experts."""
    print("=" * 50)
    print("Available Experts (4)")
    print("=" * 50)
    for e in registry.list_all():
        print(f"\n  [{e.id}] {e.name}")
        print(f"  {e.description}")
        print(f"  Prompt: {e.prompt[:100]}... ({len(e.prompt)} chars)")


def search_experts():
    """Search experts."""
    print("\n" + "=" * 50)
    print("Search")
    print("=" * 50)
    for q in ["python", "security", "design"]:
        results = registry.search(q)
        print(f"\n  '{q}' → {[e.id for e in results]}")


def sample_response():
    """Sample response format."""
    print("\n" + "=" * 50)
    print("Sample consult_expert response")
    print("=" * 50)
    import json
    print(json.dumps({
        "success": True,
        "expert_id": "architect",
        "expert_name": "Software Architect",
        "model_used": "gpt-4o-mini",
        "content": "Here is architectural advice...",
        "usage": {"prompt_tokens": 500, "completion_tokens": 300, "total_tokens": 800, "cost_usd": 0.00015},
        "fallback_used": False,
        "retrieval_time_ms": 1234.5,
    }, indent=2))


if __name__ == "__main__":
    print("\n🔥 Expert Advisor (Lean Edition) — Examples\n")
    show_experts()
    search_experts()
    sample_response()
    print("\n" + "=" * 50)
    print("Done!")
    print("=" * 50)
