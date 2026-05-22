"""Configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from env vars and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Provider API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    deepseek_api_key: str | None = None
    groq_api_key: str | None = None

    # Server
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # Rate Limiting
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 30

    # Caching
    cache_ttl_seconds: int = 300
    cache_max_entries: int = 1000

    # Default LLM
    default_model: str = "gpt-4o-mini"
    default_temperature: float = 0.7
    max_tokens: int = 2048

    # Retry
    max_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0

    # Cost Tracking
    budget_warning_threshold: float = 5.0  # USD
    budget_limit: float | None = None  # No hard limit by default


settings = Settings()
