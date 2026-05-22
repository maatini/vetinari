"""Tests for config module."""

from __future__ import annotations

import pytest

from expert_advisor.config import Settings, settings


class TestSettings:
    """Tests for pydantic-settings configuration."""

    def test_defaults(self) -> None:
        """Test default configuration values."""
        assert settings.log_level == "INFO"
        assert settings.default_model == "gpt-4o-mini"
        assert settings.default_temperature == 0.7
        assert settings.max_tokens == 2048
        assert settings.rate_limit_window_seconds == 60
        assert settings.rate_limit_max_requests == 30
        assert settings.cache_ttl_seconds == 300
        assert settings.cache_max_entries == 1000
        assert settings.max_retries == 3
        assert settings.retry_base_delay_seconds == 1.0
        assert settings.retry_max_delay_seconds == 30.0
        assert settings.budget_warning_threshold == 5.0
        assert settings.budget_limit is None

    def test_api_keys_default_none(self) -> None:
        """API keys should default to None."""
        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None
        assert settings.google_api_key is None
        # deepseek key may come from env, skip that assertion
        assert settings.groq_api_key is None

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DEFAULT_MODEL", "gpt-4o")
        s = Settings()
        assert s.log_level == "DEBUG"
        assert s.default_model == "gpt-4o"

    def test_extra_fields_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Extra env vars should be silently ignored."""
        monkeypatch.setenv("UNKNOWN_FIELD", "value")
        s = Settings()
        # Should not raise
        assert s.log_level == "INFO"
