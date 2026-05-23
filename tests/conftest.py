"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from vetinari.llm import LLMRouter


@pytest.fixture
def router() -> LLMRouter:
    """Router instance for testing."""
    return LLMRouter()
