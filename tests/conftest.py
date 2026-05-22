"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from expert_advisor.llm import CostLog, LLMRouter


@pytest.fixture
def cost_log() -> CostLog:
    """Fresh cost log for each test."""
    return CostLog()


@pytest.fixture
def router() -> LLMRouter:
    """Router instance for testing."""
    return LLMRouter()
