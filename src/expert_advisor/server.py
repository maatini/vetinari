"""MCP Server — Multi-Expert Advisor (Lean Edition).

Tools:
- list_experts: List/search experts
- consult_expert: Get advice from a single expert
- consult_multiple_experts: Parallel expert queries (killer feature)
- get_expert_prompt: View system prompt
- cost_summary: Minimal cost/token log
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from expert_advisor.config import settings
from expert_advisor.experts import registry
from expert_advisor.llm import ExpertAdviceResponse, LLMRouter
from expert_advisor.utils.logging import configure_logging

# ── Initialization ───────────────────────────────────────────────────────────

configure_logging(settings.log_level)
mcp = FastMCP("Expert Advisor (Lean)")
router = LLMRouter(enable_cache=settings.enable_cache)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_response(resp: ExpertAdviceResponse) -> dict[str, Any]:
    """Format an ExpertAdviceResponse into a JSON-safe dict."""
    usage = resp.usage
    return {
        "success": resp.success,
        "expert_id": resp.expert_id,
        "expert_name": resp.expert_name,
        "model_used": resp.model_used,
        "content": resp.content,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.prompt_tokens + usage.completion_tokens,
            "cost_usd": round(usage.cost_usd, 6),
        },
        "fallback_used": resp.fallback_used,
        "retrieval_time_ms": round(resp.retrieval_time_ms, 1),
        "error": resp.error,
    }


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool(
    name="list_experts",
    description="List all available expert domains. Optionally filter by a search query.",
)
async def list_experts(query: str | None = None) -> str:
    """List experts, optionally filtered by search query."""
    experts = registry.search(query) if query else registry.list_all()
    result = [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "tags": e.tags,
        }
        for e in experts
    ]
    return json.dumps(result, indent=2)


@mcp.tool(
    name="consult_expert",
    description="Get detailed advice from a single expert by ID.",
)
async def consult_expert(
    expert_id: str,
    query: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Consult a single expert."""
    expert = registry.get(expert_id)
    if expert is None:
        return json.dumps({
            "success": False,
            "error": f"Unknown expert '{expert_id}'. Use list_experts to see available experts.",
            "available_ids": registry.get_ids(),
        }, indent=2)

    response = await router.consult(
        expert=expert,
        user_query=query,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return json.dumps(_format_response(response), indent=2)


@mcp.tool(
    name="consult_multiple_experts",
    description="Get advice from multiple experts in parallel. Provide expert IDs and a query.",
)
async def consult_multiple_experts(
    expert_ids: list[str],
    query: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Consult multiple experts in parallel."""
    experts = []
    unknown = []
    for eid in expert_ids:
        expert = registry.get(eid)
        if expert:
            experts.append(expert)
        else:
            unknown.append(eid)

    if not experts:
        return json.dumps({
            "success": False,
            "error": "No valid expert IDs provided.",
            "unknown_ids": unknown,
            "available_ids": registry.get_ids(),
        }, indent=2)

    responses = await router.consult_multiple(
        experts=experts,
        user_query=query,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return json.dumps({
        "success": True,
        "query": query,
        "responses": [_format_response(r) for r in responses],
        "unknown_ids": unknown,
    }, indent=2)


@mcp.tool(
    name="cost_summary",
    description="Get cumulative cost and token usage statistics.",
)
async def cost_summary() -> str:
    """Return cost tracking summary."""
    return json.dumps({"summary": router.cost_log.summary}, indent=2)


@mcp.tool(
    name="get_expert_prompt",
    description="Get the full system prompt for a specific expert. Useful for debugging.",
)
async def get_expert_prompt(expert_id: str) -> str:
    """Get the system prompt for an expert."""
    expert = registry.get(expert_id)
    if expert is None:
        return json.dumps({
            "error": f"Unknown expert '{expert_id}'",
            "available_ids": registry.get_ids(),
        }, indent=2)
    return json.dumps({
        "expert_id": expert.id,
        "expert_name": expert.name,
        "prompt": expert.prompt,
        "recommended_model": expert.recommended_model,
    }, indent=2)


# ── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
