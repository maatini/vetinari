"""Lean configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # LLM resilience (retries via LiteLLM + model fallback backoff)
    llm_max_retries: int = 2
    llm_retry_base_delay_seconds: float = 0.5
    llm_timeout_seconds: float | None = 90.0

    # Optional cache (off by default)
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 500
    enable_cache: bool = False


settings = Settings()
