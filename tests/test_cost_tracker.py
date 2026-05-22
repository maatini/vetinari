"""Tests for CostLog (Lean Edition)."""

from __future__ import annotations

import pytest

from expert_advisor.llm import CostLog, UsageInfo


class TestUsageInfo:
    """Tests for UsageInfo dataclass."""

    def test_defaults(self) -> None:
        u = UsageInfo()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.cost_usd == 0.0
        assert u.model == "unknown"


class TestCostLog:
    """Tests for CostLog."""

    def test_initial_state(self, cost_log: CostLog) -> None:
        assert cost_log.total_tokens == 0
        assert cost_log.total_cost == 0.0
        assert cost_log.total_calls == 0
        assert cost_log.successful_calls == 0

    def test_record_success(self, cost_log: CostLog) -> None:
        usage = cost_log.record(prompt_tokens=100, completion_tokens=50, cost=0.005)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.cost_usd == 0.005
        assert cost_log.total_calls == 1
        assert cost_log.successful_calls == 1
        assert cost_log.total_tokens == 150
        assert cost_log.total_cost == 0.005

    def test_record_failure(self, cost_log: CostLog) -> None:
        cost_log.record(success=False)
        assert cost_log.total_calls == 1
        assert cost_log.successful_calls == 0
        assert cost_log.total_tokens == 0
        assert cost_log.total_cost == 0.0

    def test_multiple_calls_accumulate(self, cost_log: CostLog) -> None:
        for _ in range(10):
            cost_log.record(prompt_tokens=10, cost=0.001)
        assert cost_log.total_calls == 10
        assert cost_log.total_tokens == 100
        assert cost_log.total_cost == pytest.approx(0.01)

    def test_summary_string(self, cost_log: CostLog) -> None:
        cost_log.record(prompt_tokens=100, cost=0.005)
        s = cost_log.summary
        assert "calls=1" in s
        assert "tokens=100" in s
        assert "0.005000" in s
