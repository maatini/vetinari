"""Tests for config module (lean)."""

from __future__ import annotations

import pytest

from vetinari.config import Settings, settings


class TestSettings:
    """Tests for pydantic-settings configuration."""

    def test_defaults(self) -> None:
        assert settings.log_level == "INFO"
        assert settings.default_model == "gpt-4o-mini"
        assert settings.default_temperature == 0.7
        assert settings.max_tokens == 2048
        assert settings.cache_ttl_seconds == 300
        assert settings.cache_max_entries == 500
        assert settings.enable_cache is False

    def test_api_keys_default_none(self) -> None:
        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None
        assert isinstance(settings.deepseek_api_key, (str, type(None)))

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DEFAULT_MODEL", "gpt-4o")
        s = Settings()
        assert s.log_level == "DEBUG"
        assert s.default_model == "gpt-4o"

    def test_extra_fields_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UNKNOWN_FIELD", "value")
        s = Settings()
        assert s.log_level == "INFO"
