"""Lean configuration via pydantic-settings."""

from __future__ import annotations

import os
from typing import Annotated

import structlog
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = structlog.get_logger(__name__)

DEFAULT_FALLBACK_MODELS = [
    "anthropic/claude-3-5-sonnet-20241022",
    "gpt-4o-mini",
    "deepseek/deepseek-chat",
]


def _has_api_key(key: str | None) -> bool:
    return bool(key and key.strip())


# LiteLLM reads provider keys from os.environ, not from pydantic Settings.
_ENV_KEY_MAP: tuple[tuple[str, str], ...] = (
    ("openai_api_key", "OPENAI_API_KEY"),
    ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    ("deepseek_api_key", "DEEPSEEK_API_KEY"),
)


class Settings(BaseSettings):
    """Application settings loaded from env vars and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Provider API Keys (at least one required)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    deepseek_api_key: str | None = None

    # Server
    log_level: str = "INFO"

    # LLM defaults
    default_model: str = "gpt-4o-mini"
    default_temperature: float = 0.7
    max_tokens: int = 2048

    # Model fallback chain (comma-separated via FALLBACK_MODELS env)
    fallback_models: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_FALLBACK_MODELS),
    )

    # LLM resilience (retries via LiteLLM + model fallback backoff)
    llm_max_retries: int = 2
    llm_retry_base_delay_seconds: float = 0.5
    llm_timeout_seconds: float | None = 90.0
    llm_max_concurrent: int = 4

    # Optional cache (off by default)
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 500
    enable_cache: bool = False

    # Input limits (consult tools)
    max_query_chars: int = 32_000
    max_output_tokens: int = 8192
    max_experts_per_request: int = 4

    @field_validator("fallback_models", mode="before")
    @classmethod
    def parse_fallback_models(cls, v: object) -> object:
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v

    @field_validator("llm_max_concurrent")
    @classmethod
    def validate_max_concurrent(cls, v: int) -> int:
        if v < 1:
            raise ValueError("llm_max_concurrent must be >= 1")
        return v

    @field_validator("max_query_chars", "max_output_tokens", "max_experts_per_request")
    @classmethod
    def validate_positive_limit(cls, v: int) -> int:
        if v < 1:
            raise ValueError("limit must be >= 1")
        return v


def sync_api_keys_to_env(s: Settings) -> None:
    """Copy configured API keys into os.environ for LiteLLM."""
    for field_name, env_name in _ENV_KEY_MAP:
        value = getattr(s, field_name)
        if _has_api_key(value):
            os.environ[env_name] = value.strip()


def validate_settings(s: Settings) -> None:
    """Validate settings at startup. Raises ValueError if misconfigured."""
    if not any(
        _has_api_key(k)
        for k in (s.openai_api_key, s.anthropic_api_key, s.deepseek_api_key)
    ):
        raise ValueError(
            "At least one API key is required (OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "or DEEPSEEK_API_KEY). See .env.example."
        )

    _warn_missing_keys_for_models(s)
    sync_api_keys_to_env(s)


def _model_needs_anthropic_key(model: str) -> bool:
    lower = model.lower()
    return "anthropic" in lower or "claude" in lower


def _model_needs_openai_key(model: str) -> bool:
    lower = model.lower()
    return lower.startswith("gpt-") or lower.startswith("openai/")


def _model_needs_deepseek_key(model: str) -> bool:
    return "deepseek" in model.lower()


def model_has_api_key(model: str, s: Settings) -> bool:
    """Return whether settings include an API key for this model's provider."""
    if _model_needs_anthropic_key(model):
        return _has_api_key(s.anthropic_api_key)
    if _model_needs_openai_key(model):
        return _has_api_key(s.openai_api_key)
    if _model_needs_deepseek_key(model):
        return _has_api_key(s.deepseek_api_key)
    return True  # unknown provider — don't block custom models


def prioritize_models_by_keys(models: list[str], s: Settings) -> list[str]:
    """Reorder models: those with matching API keys first, preserving relative order."""
    with_key = [m for m in models if model_has_api_key(m, s)]
    without_key = [m for m in models if not model_has_api_key(m, s)]
    return with_key + without_key


def _warn_missing_keys_for_models(s: Settings) -> None:
    """Warn when fallback models may lack a matching API key (non-fatal)."""
    for model in s.fallback_models:
        if _model_needs_anthropic_key(model) and not _has_api_key(s.anthropic_api_key):
            logger.warning("fallback_model_without_key", model=model, provider="anthropic")
        if _model_needs_openai_key(model) and not _has_api_key(s.openai_api_key):
            logger.warning("fallback_model_without_key", model=model, provider="openai")
        if _model_needs_deepseek_key(model) and not _has_api_key(s.deepseek_api_key):
            logger.warning("fallback_model_without_key", model=model, provider="deepseek")


settings = Settings()
sync_api_keys_to_env(settings)
