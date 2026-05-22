"""Cost tracking for LLM API calls."""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from expert_advisor.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class UsageInfo:
    """Token usage for a single call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = "unknown"
    cached: bool = False
    success: bool = True


@dataclass
class CostTracker:
    """Tracks cumulative costs across all LLM calls."""

    total_cost: float = 0.0
    total_tokens: int = 0
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    cached_calls: int = 0
    breakdown: dict[str, float] = field(default_factory=dict)

    def record(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        cached: bool = False,
        success: bool = True,
    ) -> UsageInfo:
        """Record a usage event and return the UsageInfo."""
        usage = UsageInfo(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            model=model,
            cached=cached,
            success=success,
        )

        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1

        if cached:
            self.cached_calls += 1
        else:
            self.total_cost += cost
            self.total_tokens += usage.total_tokens
            self.breakdown[model] = self.breakdown.get(model, 0.0) + cost

        # Log warning if budget threshold is exceeded
        if not cached and self.total_cost >= settings.budget_warning_threshold:
            logger.warning(
                "budget_warning",
                total_cost=self.total_cost,
                threshold=settings.budget_warning_threshold,
            )

        # Check budget limit
        if settings.budget_limit is not None and self.total_cost >= settings.budget_limit:
            logger.error(
                "budget_limit_exceeded",
                total_cost=self.total_cost,
                limit=settings.budget_limit,
            )

        return usage

    def get_summary(self) -> dict:
        """Return a summary of all tracked costs."""
        return {
            "total_cost_usd": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "cached_calls": self.cached_calls,
            "cost_by_model": {k: round(v, 6) for k, v in self.breakdown.items()},
        }
