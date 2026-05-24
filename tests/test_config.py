"""Tests for config module (lean)."""

from __future__ import annotations

import os

import pytest

from vetinari.config import (
    DEFAULT_FALLBACK_MODELS,
    Settings,
    model_has_api_key,
    prioritize_models_by_keys,
    settings,
    sync_api_keys_to_env,
    validate_settings,
)


class TestSettings:
    """Tests for pydantic-settings configuration."""

    def test_defaults(self) -> None:
        assert settings.log_level == "INFO"
        assert settings.default_model == "gpt-4o-mini"
        assert settings.default_temperature == 0.7
        assert settings.max_tokens == 2048
        assert settings.fallback_models == DEFAULT_FALLBACK_MODELS
        assert settings.llm_max_concurrent == 4
        assert settings.cache_ttl_seconds == 300
        assert settings.cache_max_entries == 500
        assert settings.enable_cache is False
        assert settings.max_query_chars == 32_000
        assert settings.max_output_tokens == 8192
        assert settings.max_experts_per_request == 4
        # LLM resilience (Phase 1)
        assert settings.llm_max_retries == 2
        assert settings.llm_retry_base_delay_seconds == 0.5
        assert settings.llm_timeout_seconds == 90.0

    def test_api_keys_default_none(self) -> None:
        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None
        assert isinstance(settings.deepseek_api_key, (str, type(None)))

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DEFAULT_MODEL", "gpt-4o")
        monkeypatch.setenv("LLM_MAX_RETRIES", "5")
        monkeypatch.setenv("LLM_RETRY_BASE_DELAY_SECONDS", "1.5")
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "30")
        s = Settings()
        assert s.log_level == "DEBUG"
        assert s.default_model == "gpt-4o"
        assert s.llm_max_retries == 5
        assert s.llm_retry_base_delay_seconds == 1.5
        assert s.llm_timeout_seconds == 30.0

    def test_extra_fields_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UNKNOWN_FIELD", "value")
        s = Settings()
        assert s.log_level == "INFO"

    def test_fallback_models_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FALLBACK_MODELS", "gpt-4o, deepseek/deepseek-chat")
        s = Settings()
        assert s.fallback_models == ["gpt-4o", "deepseek/deepseek-chat"]

    def test_llm_max_concurrent_invalid(self) -> None:
        with pytest.raises(ValueError, match="llm_max_concurrent"):
            Settings(llm_max_concurrent=0)

    def test_max_query_chars_invalid(self) -> None:
        with pytest.raises(ValueError, match="limit must be"):
            Settings(max_query_chars=0)


class TestValidateSettings:
    """Tests for startup validation."""

    def test_validate_settings_no_keys_raises(self) -> None:
        s = Settings(
            openai_api_key=None,
            anthropic_api_key=None,
            deepseek_api_key=None,
        )
        with pytest.raises(ValueError, match="At least one API key"):
            validate_settings(s)

    def test_validate_settings_with_one_key_ok(self) -> None:
        s = Settings(openai_api_key="sk-test")
        validate_settings(s)

    def test_validate_settings_empty_string_treated_as_missing(self) -> None:
        s = Settings(
            openai_api_key="  ",
            anthropic_api_key="",
            deepseek_api_key=None,
        )
        with pytest.raises(ValueError, match="At least one API key"):
            validate_settings(s)


class TestSyncApiKeysToEnv:
    """API keys from .env must reach LiteLLM via os.environ."""

    def test_sync_sets_openai_key_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings(openai_api_key="sk-from-settings")
        sync_api_keys_to_env(s)
        assert os.environ.get("OPENAI_API_KEY") == "sk-from-settings"

    def test_sync_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        s = Settings(anthropic_api_key="  sk-ant-test  ")
        sync_api_keys_to_env(s)
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-test"

    def test_sync_skips_empty_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        s = Settings(deepseek_api_key=None)
        sync_api_keys_to_env(s)
        assert "DEEPSEEK_API_KEY" not in os.environ

    def test_validate_settings_syncs_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings(openai_api_key="sk-via-validate")
        validate_settings(s)
        assert os.environ.get("OPENAI_API_KEY") == "sk-via-validate"


class TestModelKeyRouting:
    """Tests for key-aware model selection helpers."""

    @staticmethod
    def _isolated_settings(**kwargs: str | None) -> Settings:
        return Settings(_env_file=None, **kwargs)

    def test_model_has_api_key_openai(self) -> None:
        s = self._isolated_settings(
            openai_api_key="sk-test",
            anthropic_api_key=None,
            deepseek_api_key=None,
        )
        assert model_has_api_key("gpt-4o-mini", s) is True
        assert model_has_api_key("anthropic/claude-sonnet-4-6", s) is False

    def test_prioritize_models_by_keys(self) -> None:
        s = self._isolated_settings(
            openai_api_key="sk-test",
            anthropic_api_key=None,
            deepseek_api_key="sk-d",
        )
        ordered = prioritize_models_by_keys(DEFAULT_FALLBACK_MODELS, s)
        assert ordered[0] == "gpt-4o-mini"
        assert ordered[1] == "deepseek/deepseek-chat"
        assert ordered[2] == "anthropic/claude-sonnet-4-6"
