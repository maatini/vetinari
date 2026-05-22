#!/usr/bin/env python3
"""Basic usage examples for the Multi-LLM Expert Advisor.

These examples demonstrate the core functionality without needing actual LLM API keys.
Run with: uv run python examples/basic_usage.py
"""

import asyncio
import json

from expert_advisor.experts.registry import registry
from expert_advisor.utils.cost_tracker import CostTracker


def example_explore_experts():
    """Example 1: Explore available experts."""
    print("=" * 60)
    print("Example 1: Explore available experts")
    print("=" * 60)

    experts = registry.list_all()
    print(f"\nTotal experts: {len(experts)}\n")
    for e in experts:
        print(f"  • {e.id:20s} — {e.name}")
        print(f"    Tags: {', '.join(e.tags)}")
        print(f"    Model: {e.recommended_model}")
        print()


def example_search_experts():
    """Example 2: Search for experts."""
    print("=" * 60)
    print("Example 2: Search for experts")
    print("=" * 60)

    for query in ["python", "security", "debug", "rust"]:
        results = registry.search(query)
        print(f"\n  Query '{query}': {len(results)} result(s)")
        for e in results:
            print(f"    → {e.id}: {e.description[:60]}...")


def example_expert_prompt():
    """Example 3: Get an expert's system prompt."""
    print("\n" + "=" * 60)
    print("Example 3: System prompt preview (first 200 chars)")
    print("=" * 60)

    architect = registry.get("architect")
    if architect:
        print(f"\n  Expert: {architect.name}")
        print(f"  Prompt preview: {architect.prompt[:200]}...")
        print(f"  Full prompt length: {len(architect.prompt)} chars")


def example_cost_tracking():
    """Example 4: Cost tracking simulation."""
    print("\n" + "=" * 60)
    print("Example 4: Cost tracking simulation")
    print("=" * 60)

    tracker = CostTracker()

    # Simulate some calls
    tracker.record("gpt-4o-mini", prompt_tokens=500, completion_tokens=200, cost=0.00015)
    tracker.record("gpt-4o-mini", prompt_tokens=300, completion_tokens=150, cost=0.00012)
    tracker.record("claude-3-5-sonnet", prompt_tokens=1000, completion_tokens=500, cost=0.01250)
    tracker.record("deepseek-chat", prompt_tokens=400, completion_tokens=100, cost=0.00002)

    summary = tracker.get_summary()
    print("\n  Cost Summary:")
    for key, value in summary.items():
        print(f"    {key}: {value}")


def example_parallel_usage():
    """Example 5: How consult_multiple works conceptually."""
    print("\n" + "=" * 60)
    print("Example 5: Parallel consultation (conceptual)")
    print("=" * 60)

    expert_ids = ["architect", "security", "devops"]
    print(f"\n  In production, consulting these experts in parallel:")
    for eid in expert_ids:
        expert = registry.get(eid)
        if expert:
            print(f"    → {expert.name} ({eid})")
    print("\n  All calls run via asyncio.gather for maximum parallelism.")
    print("  Each expert uses their recommended model or falls back automatically.")


def example_expert_response_format():
    """Example 6: Response format explanation."""
    print("\n" + "=" * 60)
    print("Example 6: Expected response format")
    print("=" * 60)

    sample = {
        "success": True,
        "expert_id": "architect",
        "expert_name": "Software Architect",
        "model_used": "gpt-4o-mini",
        "content": "Here is the architectural advice...",
        "usage": {
            "prompt_tokens": 500,
            "completion_tokens": 300,
            "total_tokens": 800,
            "cost_usd": 0.00015,
            "cached": False,
        },
        "fallback_used": False,
        "retrieval_time_ms": 1234.5,
        "error": None,
    }
    print("\n  Sample consult_expert response:")
    print(json.dumps(sample, indent=2))


def example_error_handling():
    """Example 7: Error handling patterns."""
    print("\n" + "=" * 60)
    print("Example 7: Error handling")
    print("=" * 60)

    print("\n  Scenarios handled automatically:")
    print("    • API key missing → tries next available model")
    print("    • Rate limited → waits and retries with backoff")
    print("    • Provider error → falls back to alternative provider")
    print("    • All models down → returns error in response.error")
    print("    • Unknown expert_id → returns error with available_ids list")
    print("\n  Cache:")
    print("    • Same query+expert → cache hit (no API cost)")
    print("    • TTL: 300s, Max entries: 1000")


async def main():
    """Run all examples."""
    print("\n🔥 Multi-LLM Expert Advisor — Usage Examples\n")
    example_explore_experts()
    example_search_experts()
    example_expert_prompt()
    example_cost_tracking()
    example_parallel_usage()
    example_expert_response_format()
    example_error_handling()
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
