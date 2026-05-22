"""Tests for CostTracker."""

from __future__ import annotations

import pytest

from expert_advisor.utils.cost_tracker import CostTracker, UsageInfo


class TestUsageInfo:
    """Tests for UsageInfo dataclass."""

    def test_defaults(self) -> None:
        """UsageInfo should have sensible defaults."""
        u = UsageInfo()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0
        assert u.cost_usd == 0.0
        assert u.model == "unknown"
        assert u.cached is False
        assert u.success is True


class TestCostTracker:
    """Tests for CostTracker."""

    def test_initial_state(self, cost_tracker: CostTracker) -> None:
        """Fresh tracker should have all zeros."""
        ct = cost_tracker
        assert ct.total_cost == 0.0
        assert ct.total_tokens == 0
        assert ct.total_calls == 0
        assert ct.successful_calls == 0
        assert ct.failed_calls == 0
        assert ct.cached_calls == 0

    def test_record_success(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        usage = ct.record("gpt-4o-mini", prompt_tokens=100, completion_tokens=50, cost=0.005)
        assert usage.success is True
        assert usage.cached is False
        assert usage.total_tokens == 150
        assert usage.cost_usd == 0.005
        assert ct.total_calls == 1
        assert ct.successful_calls == 1
        assert ct.failed_calls == 0

    def test_record_failure(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        usage = ct.record("gpt-4o-mini", success=False)
        assert usage.success is False
        assert ct.total_calls == 1
        assert ct.successful_calls == 0
        assert ct.failed_calls == 1

    def test_record_cached(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        usage = ct.record(
            "gpt-4o-mini", prompt_tokens=100, completion_tokens=50,
            cost=0.005, cached=True,
        )
        assert usage.cached is True
        assert ct.cached_calls == 1
        # Cached calls should NOT count toward total cost/tokens
        assert ct.total_cost == 0.0
        assert ct.total_tokens == 0

    def test_cost_by_model_breakdown(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        ct.record("gpt-4o-mini", cost=0.001)
        ct.record("claude-3-5-sonnet", cost=0.015)
        ct.record("gpt-4o-mini", cost=0.002)
        summary = ct.get_summary()
        assert "gpt-4o-mini" in summary["cost_by_model"]
        assert summary["cost_by_model"]["gpt-4o-mini"] == 0.003
        assert summary["cost_by_model"]["claude-3-5-sonnet"] == 0.015

    def test_get_summary_structure(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        ct.record("gpt-4o-mini", prompt_tokens=100, cost=0.001)
        summary = ct.get_summary()
        assert "total_cost_usd" in summary
        assert "total_tokens" in summary
        assert "total_calls" in summary
        assert "successful_calls" in summary
        assert "failed_calls" in summary
        assert "cached_calls" in summary
        assert "cost_by_model" in summary
        assert summary["total_tokens"] == 100

    def test_multiple_calls_accumulate(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        for _ in range(10):
            ct.record("gpt-4o-mini", prompt_tokens=10, cost=0.001)
        assert ct.total_calls == 10
        assert ct.total_tokens == 100
        assert ct.total_cost == pytest.approx(0.01)

    def test_mixed_success_failure(self, cost_tracker: CostTracker) -> None:
        ct = cost_tracker
        ct.record("gpt-4o-mini", cost=0.001, success=True)
        ct.record("gpt-4o-mini", cost=0.000, success=False)
        ct.record("claude-3-5-sonnet", cost=0.015, success=True)
        assert ct.total_calls == 3
        assert ct.successful_calls == 2
        assert ct.failed_calls == 1
        # Failed calls don't add cost
        assert ct.total_cost == 0.016
