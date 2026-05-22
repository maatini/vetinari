"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from expert_advisor.routers.llm_router import LLMRouter
from expert_advisor.utils.cost_tracker import CostTracker


@pytest.fixture
def cost_tracker() -> CostTracker:
    """Fresh cost tracker for each test."""
    return CostTracker()


@pytest.fixture
def router() -> LLMRouter:
    """Router with mocked litellm."""
    # The router will lazily import litellm; tests mock as needed
    return LLMRouter()
